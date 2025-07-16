from django.core.management.base import BaseCommand
from django.utils import timezone
from core.models import MarketAlert, BellwetherAsset
from openai import OpenAI
import json
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Generate market alerts using LLM analysis of bellwether assets'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Run analysis but do not create alert',
        )

    def handle(self, *args, **options):
        try:
            # Get all bellwether assets and their data
            assets = BellwetherAsset.objects.all()
            if not assets:
                self.stdout.write(self.style.WARNING('No bellwether assets found'))
                return

            # Prepare asset data for LLM - use all available assets.
            asset_data = []
            for asset in assets:
                asset_data.append({
                    "symbol": asset.symbol,
                    "name": asset.name,
                    "type": asset.data_type,
                    "descriptors": asset.descriptors,
                    "data": asset.data[:5]
                })

            # Create prompt for LLM
            prompt = f"""Analyze these market assets and provide both a push notification summary and detailed analysis:
            Asset Data:
            {json.dumps(asset_data, indent=2)}
            Please provide your analysis in this JSON format:
            {{
                "risk_level": "HIGH/MEDIUM/LOW",
                "push_notification": "VERY SHORT 60-80 char summary for push notification. Include risk level and key insight.",
                "extended_summary": "2-3 sentence extended summary that user sees after clicking notification",
                "analysis": {{
                    "market_conditions": "Overall market state and sentiment",
                    "key_movements": ["List of significant price/indicator movements"],
                    "correlations": ["Notable correlations between assets"],
                    "risk_factors": ["Current market risks"],
                    "opportunities": ["Potential opportunities identified"]
                }}
            }}
            Example push notification format:
            "🔴 HIGH RISK: SPY and QQQ showing bearish divergence with increased volatility"
            "🟡 MEDIUM RISK: Crypto assets recovering while traditional markets consolidate"
            "🟢 LOW RISK: Markets stable with positive momentum across major indices"
            Focus on providing actionable insights and clear risk assessment.
            """

            # Get LLM analysis
            client = OpenAI(timeout=30.0)  # Add 30-second timeout
            completion = client.chat.completions.create(
                model="gpt-4.1-mini",
                messages=[
                    {"role": "system", "content": "You are an expert market analyst. Provide clear, concise insights suitable for both push notifications and detailed analysis. Focus on actionable insights and clear risk assessment."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7  # Balance between creativity and consistency
            )

            # Parse LLM response
            try:
                llm_analysis = json.loads(completion.choices[0].message.content)

                # Validate required fields
                required_fields = ['risk_level', 'push_notification', 'extended_summary', 'analysis']
                if not all(field in llm_analysis for field in required_fields):
                    raise ValueError("Missing required fields in LLM response")

                # Validate risk level
                if llm_analysis['risk_level'] not in ['HIGH', 'MEDIUM', 'LOW']:
                    raise ValueError(f"Invalid risk level: {llm_analysis['risk_level']}")

            except json.JSONDecodeError:
                self.stdout.write(self.style.ERROR('Error parsing LLM response - invalid JSON'))
                return
            except ValueError as e:
                self.stdout.write(self.style.ERROR(f'Error validating LLM response: {str(e)}'))
                return
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'Unexpected error parsing LLM response: {str(e)}'))
                return

            # If dry run, just print the analysis
            if options['dry_run']:
                self.stdout.write(self.style.SUCCESS('Dry run - Analysis results:'))
                self.stdout.write(json.dumps(llm_analysis, indent=2))
                return

            # Create market alert
            try:
                alert = MarketAlert.objects.create(
                    risk_level=llm_analysis['risk_level'],
                    short_summary=llm_analysis['push_notification'],
                    full_analysis={
                        "extended_summary": llm_analysis['extended_summary'],
                        **llm_analysis['analysis']
                    }
                )
                alert.assets_analyzed.set(assets)

                self.stdout.write(
                    self.style.SUCCESS(f'Created market alert: {alert.get_notification_text()}')
                )

                # Log detailed information
                logger.info(f"Market alert created - ID: {alert.id}, Risk Level: {alert.risk_level}")
                logger.debug(f"Full analysis for alert {alert.id}: {json.dumps(alert.full_analysis)}")

            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'Error creating market alert: {str(e)}')
                )
                logger.error(f"Failed to create market alert: {str(e)}", exc_info=True)

        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error generating market alert: {str(e)}')
            )
            logger.error("Failed to generate market alert", exc_info=True)