"""
Django management command to populate historical market data for backtesting.
This command processes existing MarketScreenerResult data and creates HistoricalMarketData
records that can be used for comprehensive backtesting analysis.
"""

import logging
from datetime import datetime, timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import transaction
from decimal import Decimal

from core.models import (
    MarketScreenerResult, HistoricalMarketData, 
    TradingSignal, PortfolioSnapshot, PortfolioPosition
)

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Populate historical market data for backtesting from existing market screener results'

    def add_arguments(self, parser):
        """Define command line arguments."""
        parser.add_argument(
            '--start-date',
            type=str,
            help='Start date for data population (YYYY-MM-DD format)',
            default=None
        )
        parser.add_argument(
            '--end-date',
            type=str,
            help='End date for data population (YYYY-MM-DD format)',
            default=None
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be created without actually creating records'
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            default=100,
            help='Number of records to process in each batch'
        )
        parser.add_argument(
            '--create-signals',
            action='store_true',
            help='Also create trading signals from screener data'
        )
        parser.add_argument(
            '--create-portfolio',
            action='store_true',
            help='Create sample portfolio snapshots from screener data'
        )

    def handle(self, *args, **options):
        """Execute the data population logic."""
        self.stdout.write(
            self.style.SUCCESS('Starting historical data population...')
        )

        # Parse date arguments
        start_date = None
        end_date = None
        
        if options['start_date']:
            try:
                start_date = datetime.strptime(options['start_date'], '%Y-%m-%d').date()
            except ValueError:
                self.stdout.write(
                    self.style.ERROR('Invalid start date format. Use YYYY-MM-DD')
                )
                return
        
        if options['end_date']:
            try:
                end_date = datetime.strptime(options['end_date'], '%Y-%m-%d').date()
            except ValueError:
                self.stdout.write(
                    self.style.ERROR('Invalid end date format. Use YYYY-MM-DD')
                )
                return

        # Get market screener results
        screener_queryset = MarketScreenerResult.objects.all().order_by('analysis_date')
        
        if start_date:
            screener_queryset = screener_queryset.filter(analysis_date__gte=start_date)
        
        if end_date:
            screener_queryset = screener_queryset.filter(analysis_date__lte=end_date)

        total_screeners = screener_queryset.count()
        
        if total_screeners == 0:
            self.stdout.write(
                self.style.WARNING('No market screener results found for the specified date range.')
            )
            return

        self.stdout.write(f"Found {total_screeners} market screener results to process")

        # Process screeners in batches
        batch_size = options['batch_size']
        processed_count = 0
        created_count = 0
        
        for i in range(0, total_screeners, batch_size):
            batch = screener_queryset[i:i + batch_size]
            
            with transaction.atomic():
                for screener in batch:
                    try:
                        # Process stocks (long positions)
                        created_count += self._process_screener_stocks(
                            screener, 'LONG', screener.top_stocks_long, options['dry_run']
                        )
                        
                        # Process stocks (short positions)
                        created_count += self._process_screener_stocks(
                            screener, 'SHORT', screener.top_stocks_short, options['dry_run']
                        )
                        
                        # Process crypto (long positions)
                        created_count += self._process_screener_crypto(
                            screener, 'LONG', screener.top_cryptos_long, options['dry_run']
                        )
                        
                        # Process crypto (short positions)
                        created_count += self._process_screener_crypto(
                            screener, 'SHORT', screener.top_cryptos_short, options['dry_run']
                        )
                        
                        # Create trading signals if requested
                        if options['create_signals']:
                            self._create_trading_signals(screener, options['dry_run'])
                        
                        # Create portfolio snapshot if requested
                        if options['create_portfolio']:
                            self._create_portfolio_snapshot(screener, options['dry_run'])
                        
                        processed_count += 1
                        
                    except Exception as e:
                        self.stdout.write(
                            self.style.ERROR(
                                f"Error processing screener {screener.id}: {str(e)}"
                            )
                        )
                        logger.error(f"Error processing screener {screener.id}: {str(e)}")

            # Progress update
            if processed_count % 10 == 0:
                self.stdout.write(f"Processed {processed_count}/{total_screeners} screeners...")

        # Final summary
        action_text = "Would create" if options['dry_run'] else "Created"
        self.stdout.write(
            self.style.SUCCESS(
                f"{action_text} {created_count} historical market data records "
                f"from {processed_count} market screener results"
            )
        )

    def _process_screener_stocks(self, screener, position_type, stocks_data, dry_run):
        """Process stock data from screener results."""
        created_count = 0
        
        for stock in stocks_data:
            if not isinstance(stock, dict):
                continue
                
            symbol = stock.get('ticker') or stock.get('symbol')
            if not symbol:
                continue
            
            # Extract available data
            price = stock.get('price', 0)
            change_percent = stock.get('change_percent', 0)
            confidence_score = stock.get('confidence_score', 0)
            rank = stock.get('rank', None)
            company_name = stock.get('company_name', '')
            
            # Check if record already exists
            existing = HistoricalMarketData.objects.filter(
                symbol=symbol,
                asset_type='STOCK',
                analysis_date=screener.analysis_date
            ).first()
            
            if existing:
                continue  # Skip if already exists
            
            if not dry_run:
                HistoricalMarketData.objects.create(
                    analysis_date=screener.analysis_date,
                    symbol=symbol,
                    asset_type='STOCK',
                    close_price=Decimal(str(price)) if price else None,
                    change_1d=Decimal(str(change_percent)) if change_percent else None,
                    screener_position=position_type,
                    confidence_score=Decimal(str(confidence_score)) if confidence_score else None,
                    rank_in_category=rank,
                    data_source='market_screener'
                )
            
            created_count += 1
        
        return created_count

    def _process_screener_crypto(self, screener, position_type, crypto_data, dry_run):
        """Process cryptocurrency data from screener results."""
        created_count = 0
        
        for crypto in crypto_data:
            if not isinstance(crypto, dict):
                continue
                
            symbol = crypto.get('symbol')
            if not symbol:
                continue
            
            # Extract available data
            price = crypto.get('price', 0)
            change_percent = crypto.get('change_percent', 0)
            market_cap = crypto.get('market_cap', 0)
            volume = crypto.get('volume', 0)
            name = crypto.get('name', '')
            
            # Check if record already exists
            existing = HistoricalMarketData.objects.filter(
                symbol=symbol,
                asset_type='CRYPTO',
                analysis_date=screener.analysis_date
            ).first()
            
            if existing:
                continue  # Skip if already exists
            
            if not dry_run:
                HistoricalMarketData.objects.create(
                    analysis_date=screener.analysis_date,
                    symbol=symbol,
                    asset_type='CRYPTO',
                    close_price=Decimal(str(price)) if price else None,
                    change_1d=Decimal(str(change_percent)) if change_percent else None,
                    market_cap=int(market_cap) if market_cap else None,
                    volume=int(volume) if volume else None,
                    screener_position=position_type,
                    data_source='market_screener'
                )
            
            created_count += 1
        
        return created_count

    def _create_trading_signals(self, screener, dry_run):
        """Create trading signals from screener data."""
        if dry_run:
            return
        
        # Create BUY signals for long positions
        for stock in screener.top_stocks_long:
            if isinstance(stock, dict) and stock.get('ticker'):
                TradingSignal.objects.get_or_create(
                    symbol=stock['ticker'],
                    asset_type='STOCK',
                    signal_date=screener.analysis_date,
                    signal_type='BUY',
                    defaults={
                        'confidence_score': Decimal(str(stock.get('confidence_score', 50))),
                        'signal_price': Decimal(str(stock.get('price', 0))),
                        'strength': 'MODERATE',
                        'reasoning': f"Market screener recommendation - {screener.market_sentiment}",
                        'source_screener': screener,
                        'status': 'ACTIVE'
                    }
                )
        
        # Create SELL signals for short positions
        for stock in screener.top_stocks_short:
            if isinstance(stock, dict) and stock.get('ticker'):
                TradingSignal.objects.get_or_create(
                    symbol=stock['ticker'],
                    asset_type='STOCK',
                    signal_date=screener.analysis_date,
                    signal_type='SELL',
                    defaults={
                        'confidence_score': Decimal(str(stock.get('confidence_score', 50))),
                        'signal_price': Decimal(str(stock.get('price', 0))),
                        'strength': 'MODERATE',
                        'reasoning': f"Market screener recommendation - {screener.market_sentiment}",
                        'source_screener': screener,
                        'status': 'ACTIVE'
                    }
                )

    def _create_portfolio_snapshot(self, screener, dry_run):
        """Create a sample portfolio snapshot from screener data."""
        if dry_run:
            return
        
        # Check if portfolio snapshot already exists for this date
        existing_portfolio = PortfolioSnapshot.objects.filter(
            portfolio_name='market_screener_strategy',
            snapshot_date=screener.analysis_date
        ).first()
        
        if existing_portfolio:
            return  # Skip if already exists
        
        # Create portfolio snapshot
        portfolio = PortfolioSnapshot.objects.create(
            snapshot_date=screener.analysis_date,
            portfolio_name='market_screener_strategy',
            strategy_type='LONG_SHORT',
            total_value=Decimal('100000.00'),  # Start with $100k
            market_sentiment_score=Decimal(str(screener.market_sentiment_score)),
            source_screener=screener
        )
        
        # Add positions for top stocks
        position_count = 0
        total_positions = min(10, len(screener.top_stocks_long) + len(screener.top_stocks_short))
        
        if total_positions > 0:
            position_weight = Decimal('0.8') / total_positions  # 80% invested, 20% cash
            
            # Add long positions
            for i, stock in enumerate(screener.top_stocks_long[:5]):
                if isinstance(stock, dict) and stock.get('ticker'):
                    price = Decimal(str(stock.get('price', 100)))
                    position_value = portfolio.total_value * position_weight
                    quantity = position_value / price
                    
                    PortfolioPosition.objects.create(
                        portfolio_snapshot=portfolio,
                        symbol=stock['ticker'],
                        asset_type='STOCK',
                        position_type='LONG',
                        quantity=quantity,
                        entry_price=price,
                        current_price=price,
                        position_value=position_value,
                        weight=position_weight,
                        confidence_score=Decimal(str(stock.get('confidence_score', 50))),
                        original_rank=i + 1
                    )
                    position_count += 1
            
            # Add short positions
            for i, stock in enumerate(screener.top_stocks_short[:5]):
                if isinstance(stock, dict) and stock.get('ticker'):
                    price = Decimal(str(stock.get('price', 100)))
                    position_value = portfolio.total_value * position_weight
                    quantity = position_value / price
                    
                    PortfolioPosition.objects.create(
                        portfolio_snapshot=portfolio,
                        symbol=stock['ticker'],
                        asset_type='STOCK',
                        position_type='SHORT',
                        quantity=quantity,
                        entry_price=price,
                        current_price=price,
                        position_value=position_value,
                        weight=position_weight,
                        confidence_score=Decimal(str(stock.get('confidence_score', 50))),
                        original_rank=i + 1
                    )
                    position_count += 1
            
            # Update portfolio exposures
            portfolio.long_exposure = portfolio.total_value * position_weight * len(screener.top_stocks_long[:5])
            portfolio.short_exposure = portfolio.total_value * position_weight * len(screener.top_stocks_short[:5])
            portfolio.cash_balance = portfolio.total_value - portfolio.long_exposure - portfolio.short_exposure
            portfolio.save()

        self.stdout.write(f"Created portfolio snapshot with {position_count} positions")

    def _calculate_performance_metrics(self, portfolio_snapshots):
        """Calculate performance metrics for a series of portfolio snapshots."""
        if len(portfolio_snapshots) < 2:
            return {}
        
        snapshots = list(portfolio_snapshots.order_by('snapshot_date'))
        
        # Calculate daily returns
        daily_returns = []
        for i in range(1, len(snapshots)):
            prev_value = snapshots[i-1].total_value
            curr_value = snapshots[i].total_value
            daily_return = (curr_value - prev_value) / prev_value
            daily_returns.append(daily_return)
        
        if not daily_returns:
            return {}
        
        # Calculate metrics
        total_return = ((snapshots[-1].total_value - snapshots[0].total_value) / snapshots[0].total_value) * 100
        avg_daily_return = sum(daily_returns) / len(daily_returns)
        
        # Calculate volatility
        variance = sum([(r - avg_daily_return) ** 2 for r in daily_returns]) / len(daily_returns)
        volatility = (variance ** 0.5) * (252 ** 0.5) * 100  # Annualized
        
        # Calculate max drawdown
        peak = snapshots[0].total_value
        max_drawdown = 0
        for snapshot in snapshots:
            if snapshot.total_value > peak:
                peak = snapshot.total_value
            drawdown = ((peak - snapshot.total_value) / peak) * 100
            max_drawdown = max(max_drawdown, drawdown)
        
        # Calculate Sharpe ratio (assuming 2% risk-free rate)
        annualized_return = (avg_daily_return * 252) * 100
        risk_free_rate = 2.0
        sharpe_ratio = (annualized_return - risk_free_rate) / volatility if volatility > 0 else 0
        
        return {
            'total_return': total_return,
            'annualized_return': annualized_return,
            'volatility': volatility,
            'max_drawdown': max_drawdown,
            'sharpe_ratio': sharpe_ratio
        } 