from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from openai import OpenAI
from core.models import CalendarMarketAlert, EconomicEvents
import json
import logging
from core.calendar_builder import get_calendar_data

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Generate calendar-based market alerts using economic event data'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Test without creating alert'
        )

    def calculate_window_volatility_rating(self, window_data, daily_strykr_score):
        """Calculate a volatility rating for a specific time window."""
        # Base multiplier from daily Strykr score (0-100 scale)
        base_score = daily_strykr_score * 2  # 0-200 range

        # Event density factor (0-150 additional points)
        events_in_window = len(window_data['events'])
        density_multiplier = min(events_in_window / 3, 1.5)
        density_score = base_score * density_multiplier

        # Impact intensity (0-150 additional points)
        high_impact_events = sum(1 for event in window_data['events'] 
                               if event.get('impact') == 'High')
        impact_multiplier = 1 + (high_impact_events * 0.5)
        impact_score = density_score * impact_multiplier

        # Final score (0-500 range)
        window_volatility_rating = min(round(impact_score, 2), 500)

        # Get descriptive intensity
        if window_volatility_rating < 100:
            intensity = "Low"
        elif window_volatility_rating < 200:
            intensity = "Moderate"
        elif window_volatility_rating < 300:
            intensity = "High"
        elif window_volatility_rating < 400:
            intensity = "Extreme"
        else:
            intensity = "Critical"

        return {
            'rating': window_volatility_rating,
            'intensity': intensity
        }

    def find_top_volatility_windows(self, events_data, window_hours=2, num_windows=2):
        """Find the top volatility windows in the given events data.
        
        Args:
            events_data: The economic calendar data
            window_hours: The duration of each window in hours (default: 2)
            num_windows: The number of windows to identify (default: 2)
            
        Returns:
            A list of windows with the highest volatility ratings
        """
        # List to store windows and their scores
        window_candidates = []
        
        # Current time for filtering
        now = timezone.now()
        current_hour = now.hour
        today = now.date()
        tomorrow = today + timedelta(days=1)
        
        # Look at events for today and tomorrow only
        for date_str, data in events_data["week"].items():
            window_date = timezone.datetime.fromisoformat(date_str.replace('Z', '+00:00')).date()
            
            # Only consider today and tomorrow for actionable alerts
            if window_date not in [today, tomorrow]:
                continue
                
            daily_score = data['volatility_score']
            
            # For each date, check multiple starting times throughout the day
            base_window_start = timezone.datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            if timezone.is_naive(base_window_start):
                base_window_start = timezone.make_aware(base_window_start)
            
            # Create multiple 2-hour windows throughout the day (every 2 hours)
            for hour in range(0, 24, 2):
                # Set window start to specific hour of the day
                window_start = base_window_start.replace(hour=hour, minute=0, second=0)
                window_end = window_start + timedelta(hours=window_hours)
                
                # Skip windows that have already started or will start too soon (less than 3 hours from now)
                # This gives users adequate advance notice
                if window_date == today and hour <= current_hour + 2:
                    continue
                    
                # Ensure the window is within the next 24 hours for actionable alerts
                window_hours_from_now = (window_date - today).days * 24 + (hour - current_hour)
                if window_hours_from_now > 24:
                    continue
                
                window_volatility = self.calculate_window_volatility_rating(
                    {'events': data['top_10_events']}, 
                    daily_score
                )
                
                # Store this window as a candidate
                window_candidates.append({
                    'start': window_start,
                    'end': window_end,
                    'strykr_score': daily_score,
                    'window_volatility': window_volatility,
                    'events': data['top_10_events'],
                    'rating': window_volatility['rating']  # Stored separately for easier sorting
                })
        
        # Sort windows by volatility rating (highest first)
        sorted_windows = sorted(window_candidates, key=lambda x: x['rating'], reverse=True)
        
        # If we don't have enough qualifying windows, relax constraints to find more
        if len(sorted_windows) < num_windows:
            # Create a new list for all possible windows without time restrictions
            all_windows = []
            
            # Look at events for the next few days
            for date_str, data in events_data["week"].items():
                window_date = timezone.datetime.fromisoformat(date_str.replace('Z', '+00:00')).date()
                
                # Skip dates we've already passed
                if window_date < today:
                    continue
                
                daily_score = data['volatility_score']
                
                # For each date, check all hours
                base_window_start = timezone.datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                if timezone.is_naive(base_window_start):
                    base_window_start = timezone.make_aware(base_window_start)
                
                for hour in range(0, 24, 2):  # Still use 2-hour intervals
                    # Skip windows already in our sorted_windows list
                    window_start = base_window_start.replace(hour=hour, minute=0, second=0)
                    
                    # Skip windows that have already passed
                    if window_date == today and hour < current_hour:
                        continue
                    
                    # Skip windows that already qualified (to avoid duplicates)
                    if any(w['start'] == window_start for w in sorted_windows):
                        continue
                        
                    window_end = window_start + timedelta(hours=window_hours)
                    
                    window_volatility = self.calculate_window_volatility_rating(
                        {'events': data['top_10_events']}, 
                        daily_score
                    )
                    
                    all_windows.append({
                        'start': window_start,
                        'end': window_end,
                        'strykr_score': daily_score,
                        'window_volatility': window_volatility,
                        'events': data['top_10_events'],
                        'rating': window_volatility['rating']
                    })
            
            # Sort all windows by volatility rating
            all_sorted_windows = sorted(all_windows, key=lambda x: x['rating'], reverse=True)
            
            # Add the best remaining windows to our list until we have enough
            for window in all_sorted_windows:
                if len(sorted_windows) >= num_windows:
                    break
                    
                # Don't add duplicate windows
                if not any(w['start'] == window['start'] for w in sorted_windows):
                    sorted_windows.append(window)
        
        # Ensure we always return exactly num_windows windows
        # If we somehow still don't have enough, duplicate the highest volatility window
        while len(sorted_windows) < num_windows and sorted_windows:  # Check if sorted_windows is not empty
            # Duplicate the highest volatility window with slightly different times
            highest_window = sorted_windows[0].copy()
            highest_window['start'] = highest_window['start'] + timedelta(minutes=30)
            highest_window['end'] = highest_window['end'] + timedelta(minutes=30)
            sorted_windows.append(highest_window)
        
        # Return the top N windows, or an empty list if nothing found
        return sorted_windows[:num_windows] if sorted_windows else []

    def should_send_alert(self):
        """Determine if we should send an alert based on frequency rules."""
        # We're now generating exactly 2 alerts at a time, each with different windows
        # This function is no longer used in the main flow, but kept for reference or future use
        
        # Check alerts in last 24 hours
        alerts_24h = CalendarMarketAlert.objects.filter(
            timestamp__gte=timezone.now() - timedelta(hours=24)
        ).count()

        if alerts_24h >= 2:  # Max 2 alerts per 24h
            return False

        # Get last alert
        last_alert = CalendarMarketAlert.objects.order_by('-timestamp').first()
        if last_alert and (timezone.now() - last_alert.timestamp) < timedelta(hours=12):
            return False  # Minimum 12 hours between alerts

        return True

    def generate_gpt_analysis(self, window_data, client):
        """Generate analysis using GPT-4."""
        # Get the current date and time for context
        current_time = timezone.now()
        
        # Format the time window in a user-friendly way
        window_start = window_data['start']
        window_end = window_data['end']
        window_date_str = window_start.strftime("%A, %B %d")
        window_time_str = f"{window_start.strftime('%H:%M')} - {window_end.strftime('%H:%M')}"
        
        # Count high impact events
        high_impact_count = sum(1 for event in window_data['events'] if event.get('impact') == 'High')
        medium_impact_count = sum(1 for event in window_data['events'] if event.get('impact') == 'Medium')
        
        # Prepare prompt data
        prompt = {
            "window": {
                "date": window_date_str,
                "time": window_time_str,
                "start": window_data['start'].isoformat(),
                "end": window_data['end'].isoformat(),
                "strykr_score": window_data['strykr_score'],
                "window_volatility": window_data['window_volatility'],
                "high_impact_count": high_impact_count,
                "medium_impact_count": medium_impact_count,
                "hours_until_window": round((window_start - current_time).total_seconds() / 3600, 1)
            },
            "events": window_data['events'],
            "current_time": current_time.isoformat()
        }

        response = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[
                {"role": "system", "content": """You are a financial market expert with deep knowledge of how economic events impact different markets. Your task is to analyze upcoming economic calendar events within a specific time window and provide actionable insights for traders.
                
                GUIDELINES:
                1. TIMING AWARENESS: Always reference the time window using "today", "tomorrow", "in X hours" appropriately based on the current time and window start time.
                2. PRIORITIZE HIGH IMPACT: Give special attention to high-impact events that could significantly move markets.
                3. CORRELATIONS: Identify relationships between multiple events occurring in the window that might compound their effects.
                4. ASSET SPECIFICITY: Be specific about which asset classes and markets are most likely to be affected.
                5. NUMBER FORMATTING: Format all numeric values with proper commas for thousands (e.g., 1,500 not 1500).
                
                OUTPUTS REQUIRED:
                1. SHORT SUMMARY (max 140 chars): Concise alert text suitable for a push notification. Include:
                   - Strykr VOR (Volatility Opportunity Rating): ⚡⚡⚡ HIGH / ⚡⚡ MEDIUM / ⚡ LOW
                   - Timing information ("Today at 14:00" or "Tomorrow morning")
                   - The most important event(s)
                   - Potential market impact
                
                2. FULL ANALYSIS (structured):
                   - MARKET CONTEXT: Brief overview of the scheduled events and their significance
                   - SPECIFIC ANALYSIS: Detailed explanation of expected market impacts and price action
                   - OPPORTUNITY MANAGEMENT: Strategies for both protecting capital and capitalizing on price movements
                   - ACTION STEPS: Concrete steps traders should consider before and during the window
                
                Provide your response in JSON format only: {"short_summary": "<SHORT SUMMARY>", "full_analysis": "<DETAILED ANALYSIS>"}
                """},
                {"role": "user", "content": f"Analyze this upcoming trading window and its economic events: {json.dumps(prompt, indent=2)}"}
            ],
            response_format = {"type": "json_object"}
        )

        response_content = response.choices[0].message.content
        # print(f"Response Content: {response_content}")
        analysis = json.loads(response_content)
        
        short_summary = analysis.get("short_summary", "")
        full_analysis = analysis.get("full_analysis", "")
        
        return short_summary, full_analysis

    def handle(self, *args, **options):
        try:
            client = OpenAI(timeout=30.0)  # Add 30-second timeout
            now = timezone.now()

            # Get current month's events
            current_month = now.strftime("%b").lower()
            current_year = now.strftime("%Y")

            try:
                # Get economic events without requiring recent updates
                economic_events = EconomicEvents.objects.get(
                    month=current_month,
                    year=current_year
                )
                events_data = economic_events.data
                self.stdout.write(f"Found economic events for {current_month} {current_year}")
            except EconomicEvents.DoesNotExist:
                self.stdout.write(f"No economic events found for {current_month} {current_year}")
                return

            # Find top volatility windows (two 2-hour windows)
            calendar_data = get_calendar_data(current_month, current_year, events_data, [])
            top_windows = self.find_top_volatility_windows(calendar_data, window_hours=2, num_windows=2)

            if not top_windows:
                self.stdout.write("No significant volatility windows found")
                return

            if options['dry_run']:
                for i, window in enumerate(top_windows):
                    self.stdout.write(
                        f"\nWould create alert #{i+1} for window {window['start']} - {window['end']}\n"
                        f"Strykr Score: {window['strykr_score']}\n"
                        f"Window Volatility: {window['window_volatility']['rating']} ({window['window_volatility']['intensity']})"
                    )
                return

            # Create alerts for each window
            alerts_created = 0
            for window in top_windows:
                # Generate analysis
                short_summary, full_analysis = self.generate_gpt_analysis(window, client)

                # Create alert
                alert = CalendarMarketAlert.objects.create(
                    analysis_period_start=timezone.make_aware(now) if timezone.is_naive(now) else now,
                    volatile_window_start=timezone.make_aware(window['start']) if timezone.is_naive(window['start']) else window['start'],
                    volatile_window_end=timezone.make_aware(window['end']) if timezone.is_naive(window['end']) else window['end'],
                    strykr_score=window['strykr_score'],
                    window_volatility_rating=window['window_volatility']['rating'],
                    window_volatility_intensity=window['window_volatility']['intensity'],
                    short_summary=short_summary,
                    full_analysis=full_analysis,
                    events_analyzed=window['events']
                )

                alerts_created += 1
                self.stdout.write(f"Calendar Alert #{alerts_created}: {alert.get_notification_text()}")

            self.stdout.write(f"Created {alerts_created} calendar alerts.")

        except Exception as e:
            self.stderr.write(f"Error generating calendar alert: {str(e)}")
            logger.error("Failed to generate calendar alert", exc_info=True) 