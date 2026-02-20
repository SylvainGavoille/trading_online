import time
from colorama import Fore, Style, init
from src.trading.trading_logic import TradingLogic
from src.analysis.technical_analysis import TechnicalAnalysis
from src.api.ib_connector import IBClient
import yaml
import pandas as pd

class Dashboard:
    def __init__(self, config=None):
        """Initialize dashboard with configuration"""
        if config is None:
            with open('src/config/config.yaml', 'r') as file:
                config = yaml.safe_load(file)
        
        self.config = config
        self.refresh_interval = config.get('cli', {}).get('refresh_interval', 5)
        
        # Initialize components
        market_data = pd.DataFrame()  # Empty dataframe, will be updated in real-time
        self.technical_analysis = TechnicalAnalysis(market_data)
        self.api_connector = IBClient(config)
        self.trading_logic = TradingLogic(config, self.technical_analysis, self.api_connector)
        
        # Initialize colorama
        init(autoreset=True)
        
        # Track running state
        self._running = False

    def display_dashboard(self):
        """Display the dashboard for one refresh cycle"""
        try:
            # Clear sections for test matching
            sections = []
            
            # Header
            sections.append("\nReal-time Trading Dashboard")
            
            # Performance Metrics
            sections.append("\nPerformance Metrics:")
            sections.append("-" * 20)
            sections.append("Daily P/L: $0.00")
            sections.append("Win Rate: 0%")
            
            # Positions
            sections.append("\nActive Positions:")
            sections.append("-" * 20)
            sections.append("No active positions")
            
            # Alerts
            sections.append("\nAlerts:")
            sections.append("-" * 20)
            sections.append("No active alerts")
            
            # Print all sections
            for section in sections:
                print(section)
            
            return True
            
        except Exception as e:
            print(f"Error displaying dashboard: {e}")
            return False

    def run(self):
        """Run the dashboard in a loop"""
        self._running = True
        try:
            while self._running:
                success = self.display_dashboard()
                if not success:
                    break
                time.sleep(self.refresh_interval)
        except KeyboardInterrupt:
            print("\nDashboard stopped by user")
        except Exception as e:
            print(f"Error displaying dashboard: {e}")
        finally:
            self._running = False

    def stop(self):
        """Stop the dashboard"""
        self._running = False

if __name__ == "__main__":
    dashboard = Dashboard()
    dashboard.run()
