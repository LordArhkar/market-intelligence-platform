"""
Data connector registry for managing multiple data sources.
"""

from typing import Optional

from mip.data.connectors.base import DataConnector
from mip.data.connectors.ccxt_connector import CCXTConnector
from mip.data.connectors.yfinance_connector import YahooFinanceConnector


class ConnectorRegistry:
    """
    Registry for managing multiple data connectors.
    
    Provides a single interface for accessing different data sources
    based on asset class and requirements.
    """
    
    _instance: Optional["ConnectorRegistry"] = None
    
    def __init__(self):
        self._connectors: dict[str, DataConnector] = {}
        self._default_connectors: dict[str, str] = {}
    
    @classmethod
    def get_instance(cls) -> "ConnectorRegistry":
        """Get singleton instance."""
        if cls._instance is None:
            cls._instance = cls()
            cls._instance._initialize_defaults()
        return cls._instance
    
    def _initialize_defaults(self) -> None:
        """Initialize default connectors."""
        # Register Yahoo Finance
        yf_connector = YahooFinanceConnector()
        self.register("yfinance", yf_connector)
        self._default_connectors["US_EQUITY"] = "yfinance"
        self._default_connectors["FOREX"] = "yfinance"
        self._default_connectors["INDEX"] = "yfinance"
        
        # Register CCXT for crypto
        ccxt_connector = CCXTConnector("binance")
        self.register("ccxt_binance", ccxt_connector)
        self._default_connectors["CRYPTO"] = "ccxt_binance"
    
    def register(self, name: str, connector: DataConnector) -> None:
        """Register a connector."""
        self._connectors[name] = connector
    
    def get(self, name: str) -> Optional[DataConnector]:
        """Get a connector by name."""
        return self._connectors.get(name)
    
    def get_default_for_asset_class(
        self,
        asset_class: str
    ) -> Optional[DataConnector]:
        """Get the default connector for an asset class."""
        connector_name = self._default_connectors.get(asset_class)
        if connector_name:
            return self._connectors.get(connector_name)
        return None
    
    def list_connectors(self) -> dict[str, dict]:
        """List all registered connectors."""
        return {
            name: {
                "name": c.name,
                "info": c.info.model_dump(),
                "asset_classes": c.info.asset_classes,
            }
            for name, c in self._connectors.items()
        }
    
    async def connect_all(self) -> None:
        """Connect all registered connectors."""
        for connector in self._connectors.values():
            await connector.connect()
    
    async def disconnect_all(self) -> None:
        """Disconnect all connectors."""
        for connector in self._connectors.values():
            await connector.disconnect()
    
    async def health_check_all(self) -> dict[str, dict]:
        """Run health check on all connectors."""
        results = {}
        for name, connector in self._connectors.items():
            results[name] = await connector.health_check()
        return results


def get_connector(name: Optional[str] = None) -> Optional[DataConnector]:
    """
    Get a connector by name or get default based on context.
    
    Args:
        name: Connector name, or None to get registry instance
    """
    registry = ConnectorRegistry.get_instance()
    if name is None:
        return None
    return registry.get(name)
