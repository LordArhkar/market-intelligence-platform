"""
Strategy registry for managing and discovering strategies.
"""

from typing import Optional

from mip.strategies.base import BaseStrategy
from mip.strategies.implementations import (
    MomentumStrategy,
    MeanReversionStrategy,
    TrendFollowingStrategy,
)


class StrategyRegistry:
    """
    Registry for managing trading strategies.
    
    Provides a single interface for registering and accessing strategies.
    """
    
    _instance: Optional["StrategyRegistry"] = None
    
    def __init__(self):
        self._strategies: dict[str, type[BaseStrategy]] = {}
        self._instances: dict[str, BaseStrategy] = {}
    
    @classmethod
    def get_instance(cls) -> "StrategyRegistry":
        """Get singleton instance."""
        if cls._instance is None:
            cls._instance = cls()
            cls._instance._register_default_strategies()
        return cls._instance
    
    def _register_default_strategies(self) -> None:
        """Register default strategies."""
        self.register("momentum", MomentumStrategy)
        self.register("mean_reversion", MeanReversionStrategy)
        self.register("trend_following", TrendFollowingStrategy)
    
    def register(self, name: str, strategy_class: type[BaseStrategy]) -> None:
        """Register a strategy class."""
        self._strategies[name] = strategy_class
    
    def get(self, name: str, **params) -> Optional[BaseStrategy]:
        """Get a strategy instance by name."""
        if name in self._instances:
            return self._instances[name]
        
        if name in self._strategies:
            instance = self._strategies[name](**params)
            self._instances[name] = instance
            return instance
        
        return None
    
    def create(self, name: str, **params) -> BaseStrategy:
        """Create a new strategy instance (not cached)."""
        if name not in self._strategies:
            raise ValueError(f"Unknown strategy: {name}")
        return self._strategies[name](**params)
    
    def list_strategies(self) -> list[dict]:
        """List all registered strategies."""
        return [
            {
                "name": name,
                "class": cls.__name__,
                "category": cls.category if hasattr(cls, "category") else "UNKNOWN",
            }
            for name, cls in self._strategies.items()
        ]
    
    def get_strategy_info(self, name: str) -> Optional[dict]:
        """Get detailed information about a strategy."""
        if name not in self._strategies:
            return None
        
        cls = self._strategies[name]
        instance = cls()  # Create instance for parameter info
        
        return {
            "name": name,
            "class": cls.__name__,
            "category": getattr(cls, "category", "UNKNOWN"),
            "version": getattr(cls, "version", "1.0"),
            "supported_asset_classes": getattr(cls, "supported_asset_classes", []),
            "supported_timeframes": getattr(cls, "supported_timeframes", []),
            "default_params": instance.params,
            "parameter_space": instance.get_parameter_space(),
        }


def get_strategy(name: str, **params) -> Optional[BaseStrategy]:
    """Get a strategy from the registry."""
    registry = StrategyRegistry.get_instance()
    return registry.get(name, **params)
