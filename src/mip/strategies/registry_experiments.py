"""
Experiment registry for tracking all strategy experiments.

All experiments are preserved - never delete failed experiments.
"""

from datetime import datetime
from pathlib import Path
from typing import Any, Optional
import json

from mip.strategies.base import BacktestResult


class ExperimentRegistry:
    """
    Registry for tracking all strategy experiments.
    
    Provides:
    - Persistent storage of all experiment results
    - Query capabilities
    - Performance tracking
    - Failure analysis
    """
    
    def __init__(self, storage_path: Optional[Path] = None):
        self.storage_path = storage_path or Path("./data/experiments")
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self._experiments: dict[str, dict] = {}
        self._load_experiments()
    
    def _load_experiments(self) -> None:
        """Load experiments from disk."""
        index_file = self.storage_path / "index.json"
        if index_file.exists():
            with open(index_file, "r") as f:
                self._experiments = json.load(f)
    
    def _save_experiments(self) -> None:
        """Save experiments to disk."""
        index_file = self.storage_path / "index.json"
        with open(index_file, "w") as f:
            json.dump(self._experiments, f, indent=2, default=str)
    
    def register(
        self,
        strategy_name: str,
        experiment_type: str,
        parameters: dict,
        result: BacktestResult,
        notes: str = ""
    ) -> str:
        """
        Register a new experiment.
        
        Returns the experiment ID.
        """
        experiment_id = f"{strategy_name}_{experiment_type}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
        
        experiment = {
            "id": experiment_id,
            "strategy_name": strategy_name,
            "experiment_type": experiment_type,
            "parameters": parameters,
            "created_at": datetime.utcnow().isoformat(),
            "completed_at": datetime.utcnow().isoformat(),
            "status": result.status,
            "notes": notes,
            "results": {
                "total_trades": result.total_trades,
                "total_return": result.total_return,
                "annualized_return": result.annualized_return,
                "sharpe_ratio": result.sharpe_ratio,
                "max_drawdown": result.max_drawdown,
                "profit_factor": result.profit_factor,
                "win_rate": result.win_rate,
                "expectancy": result.expectancy,
            },
            "conclusion": "PASS" if result.total_return > 0 else "FAIL",
        }
        
        self._experiments[experiment_id] = experiment
        self._save_experiments()
        
        return experiment_id
    
    def get(self, experiment_id: str) -> Optional[dict]:
        """Get an experiment by ID."""
        return self._experiments.get(experiment_id)
    
    def list_experiments(
        self,
        strategy_name: Optional[str] = None,
        experiment_type: Optional[str] = None,
        limit: int = 100
    ) -> list[dict]:
        """List experiments with optional filtering."""
        experiments = list(self._experiments.values())
        
        if strategy_name:
            experiments = [
                e for e in experiments
                if e["strategy_name"] == strategy_name
            ]
        
        if experiment_type:
            experiments = [
                e for e in experiments
                if e["experiment_type"] == experiment_type
            ]
        
        # Sort by date, newest first
        experiments.sort(
            key=lambda x: x.get("created_at", ""),
            reverse=True
        )
        
        return experiments[:limit]
    
    def get_strategy_summary(self, strategy_name: str) -> dict:
        """Get summary statistics for a strategy."""
        experiments = [
            e for e in self._experiments.values()
            if e["strategy_name"] == strategy_name
        ]
        
        if not experiments:
            return {
                "strategy": strategy_name,
                "total_experiments": 0,
            }
        
        passing = [e for e in experiments if e["conclusion"] == "PASS"]
        failing = [e for e in experiments if e["conclusion"] == "FAIL"]
        
        best_return = max(e["results"]["total_return"] for e in experiments) if experiments else 0
        best_sharpe = max(e["results"]["sharpe_ratio"] for e in experiments if e["results"]["sharpe_ratio"]) if experiments else 0
        
        return {
            "strategy": strategy_name,
            "total_experiments": len(experiments),
            "passing": len(passing),
            "failing": len(failing),
            "pass_rate": len(passing) / len(experiments) if experiments else 0,
            "best_return": best_return,
            "best_sharpe": best_sharpe,
            "last_experiment": experiments[0]["created_at"] if experiments else None,
        }
    
    def get_all_strategies_summary(self) -> list[dict]:
        """Get summary for all strategies."""
        strategies = set(e["strategy_name"] for e in self._experiments.values())
        return [
            self.get_strategy_summary(s) for s in strategies
        ]
    
    def export_csv(self, filepath: Path) -> None:
        """Export all experiments to CSV."""
        import csv
        
        if not self._experiments:
            return
        
        fieldnames = [
            "id", "strategy_name", "experiment_type", "created_at",
            "status", "total_trades", "total_return", "sharpe_ratio",
            "max_drawdown", "profit_factor", "win_rate", "conclusion"
        ]
        
        with open(filepath, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            
            for exp in self._experiments.values():
                row = {
                    "id": exp["id"],
                    "strategy_name": exp["strategy_name"],
                    "experiment_type": exp["experiment_type"],
                    "created_at": exp["created_at"],
                    "status": exp["status"],
                    "total_trades": exp["results"]["total_trades"],
                    "total_return": f"{exp['results']['total_return']:.2f}%",
                    "sharpe_ratio": f"{exp['results']['sharpe_ratio']:.2f}" if exp["results"]["sharpe_ratio"] else "N/A",
                    "max_drawdown": f"{exp['results']['max_drawdown']:.2f}%",
                    "profit_factor": f"{exp['results']['profit_factor']:.2f}" if exp["results"]["profit_factor"] else "N/A",
                    "win_rate": f"{exp['results']['win_rate']:.2f}%" if exp["results"]["win_rate"] else "N/A",
                    "conclusion": exp["conclusion"],
                }
                writer.writerow(row)
    
    def get_failed_experiments(self, limit: int = 50) -> list[dict]:
        """Get recently failed experiments for analysis."""
        failed = [
            e for e in self._experiments.values()
            if e["conclusion"] == "FAIL"
        ]
        failed.sort(
            key=lambda x: x.get("created_at", ""),
            reverse=True
        )
        return failed[:limit]
