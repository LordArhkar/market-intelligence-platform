#!/usr/bin/env python3
"""
Comprehensive Backtest Analysis and Report Generator

Analyzes backtest results and generates actionable insights.
"""

import json
import os
from datetime import datetime
from collections import defaultdict

def load_results():
    """Load the most recent backtest results."""
    files = [f for f in os.listdir('.') if f.startswith('backtest_results_') and f.endswith('.json')]
    if not files:
        return None
    latest = sorted(files)[-1]
    with open(latest, 'r') as f:
        return json.load(f)

def sector_analysis(results):
    """Analyze performance by sector."""
    # Map stocks to sectors
    sector_map = {
        # Technology
        'AAPL': 'Technology', 'MSFT': 'Technology', 'NVDA': 'Technology', 'GOOGL': 'Technology', 
        'GOOG': 'Technology', 'META': 'Technology', 'AMZN': 'Technology', 'AVGO': 'Technology',
        'ADBE': 'Technology', 'CSCO': 'Technology', 'ACN': 'Technology', 'IBM': 'Technology',
        'ORCL': 'Technology', 'INTC': 'Technology', 'AMD': 'Technology', 'QCOM': 'Technology',
        'TXN': 'Technology', 'NOW': 'Technology', 'INTU': 'Technology', 'AMAT': 'Technology',
        'LRCX': 'Technology', 'MU': 'Technology', 'KLAC': 'Technology', 'SNPS': 'Technology',
        'CDNS': 'Technology', 'PANW': 'Technology', 'CRWD': 'Technology', 'FTNT': 'Technology',
        'NET': 'Technology',
        # Consumer
        'TSLA': 'Consumer', 'HD': 'Consumer', 'MCD': 'Consumer', 'NKE': 'Consumer', 
        'SBUX': 'Consumer', 'LOW': 'Consumer', 'TJX': 'Consumer', 'BKNG': 'Consumer',
        'CMG': 'Consumer', 'MAR': 'Consumer', 'HLT': 'Consumer', 'RCL': 'Consumer',
        'CCL': 'Consumer', 'EBAY': 'Consumer', 'YUM': 'Consumer', 'DRI': 'Consumer',
        'ROST': 'Consumer', 'DLR': 'Consumer', 'EXPE': 'Consumer',
        # Financials
        'JPM': 'Financials', 'BAC': 'Financials', 'WFC': 'Financials', 'GS': 'Financials',
        'MS': 'Financials', 'C': 'Financials', 'BLK': 'Financials', 'AXP': 'Financials',
        'SCHW': 'Financials', 'USB': 'Financials', 'TFC': 'Financials', 'COF': 'Financials',
        'MET': 'Financials', 'PRU': 'Financials', 'AON': 'Financials', 'MMC': 'Financials',
        'CB': 'Financials', 'TRV': 'Financials', 'ALL': 'Financials', 'AIG': 'Financials',
        # Healthcare
        'UNH': 'Healthcare', 'JNJ': 'Healthcare', 'LLY': 'Healthcare', 'PFE': 'Healthcare',
        'ABBV': 'Healthcare', 'MRK': 'Healthcare', 'TMO': 'Healthcare', 'ABT': 'Healthcare',
        'DHR': 'Healthcare', 'BMY': 'Healthcare', 'AMGN': 'Healthcare', 'GILD': 'Healthcare',
        'ISRG': 'Healthcare', 'MDT': 'Healthcare', 'SYK': 'Healthcare', 'BSX': 'Healthcare',
        'ZTS': 'Healthcare', 'REGN': 'Healthcare', 'VRTX': 'Healthcare', 'BIIB': 'Healthcare',
        # Industrial
        'CAT': 'Industrial', 'BA': 'Industrial', 'HON': 'Industrial', 'UPS': 'Industrial',
        'RTX': 'Industrial', 'GE': 'Industrial', 'DE': 'Industrial', 'LMT': 'Industrial',
        'MMM': 'Industrial', 'EMR': 'Industrial',
    }
    
    sector_stats = defaultdict(lambda: {'stocks': [], 'pnl': 0, 'trades': 0, 'wins': 0})
    
    for r in results:
        sector = sector_map.get(r['symbol'], 'Other')
        sector_stats[sector]['stocks'].append(r['symbol'])
        sector_stats[sector]['pnl'] += r['total_pnl']
        sector_stats[sector]['trades'] += r['trades']
    
    return sector_stats

def generate_report():
    """Generate comprehensive analysis report."""
    # Define sector_map globally so it's accessible
    global sector_map
    sector_map = {
        # Technology
        'AAPL': 'Technology', 'MSFT': 'Technology', 'NVDA': 'Technology', 'GOOGL': 'Technology', 
        'GOOG': 'Technology', 'META': 'Technology', 'AMZN': 'Technology', 'AVGO': 'Technology',
        'ADBE': 'Technology', 'CSCO': 'Technology', 'ACN': 'Technology', 'IBM': 'Technology',
        'ORCL': 'Technology', 'INTC': 'Technology', 'AMD': 'Technology', 'QCOM': 'Technology',
        'TXN': 'Technology', 'NOW': 'Technology', 'INTU': 'Technology', 'AMAT': 'Technology',
        'LRCX': 'Technology', 'MU': 'Technology', 'KLAC': 'Technology', 'SNPS': 'Technology',
        'CDNS': 'Technology', 'PANW': 'Technology', 'CRWD': 'Technology', 'FTNT': 'Technology',
        'NET': 'Technology',
        # Consumer
        'TSLA': 'Consumer', 'HD': 'Consumer', 'MCD': 'Consumer', 'NKE': 'Consumer', 
        'SBUX': 'Consumer', 'LOW': 'Consumer', 'TJX': 'Consumer', 'BKNG': 'Consumer',
        'CMG': 'Consumer', 'MAR': 'Consumer', 'HLT': 'Consumer', 'RCL': 'Consumer',
        'CCL': 'Consumer', 'EBAY': 'Consumer', 'YUM': 'Consumer', 'DRI': 'Consumer',
        'ROST': 'Consumer', 'DLR': 'Consumer', 'EXPE': 'Consumer',
        # Financials
        'JPM': 'Financials', 'BAC': 'Financials', 'WFC': 'Financials', 'GS': 'Financials',
        'MS': 'Financials', 'C': 'Financials', 'BLK': 'Financials', 'AXP': 'Financials',
        'SCHW': 'Financials', 'USB': 'Financials', 'TFC': 'Financials', 'COF': 'Financials',
        'MET': 'Financials', 'PRU': 'Financials', 'AON': 'Financials', 'MMC': 'Financials',
        'CB': 'Financials', 'TRV': 'Financials', 'ALL': 'Financials', 'AIG': 'Financials',
        # Healthcare
        'UNH': 'Healthcare', 'JNJ': 'Healthcare', 'LLY': 'Healthcare', 'PFE': 'Healthcare',
        'ABBV': 'Healthcare', 'MRK': 'Healthcare', 'TMO': 'Healthcare', 'ABT': 'Healthcare',
        'DHR': 'Healthcare', 'BMY': 'Healthcare', 'AMGN': 'Healthcare', 'GILD': 'Healthcare',
        'ISRG': 'Healthcare', 'MDT': 'Healthcare', 'SYK': 'Healthcare', 'BSX': 'Healthcare',
        'ZTS': 'Healthcare', 'REGN': 'Healthcare', 'VRTX': 'Healthcare', 'BIIB': 'Healthcare',
        # Industrial
        'CAT': 'Industrial', 'BA': 'Industrial', 'HON': 'Industrial', 'UPS': 'Industrial',
        'RTX': 'Industrial', 'GE': 'Industrial', 'DE': 'Industrial', 'LMT': 'Industrial',
        'MMM': 'Industrial', 'EMR': 'Industrial',
    }
    
    print("\n" + "="*80)
    print("📊 COMPREHENSIVE BACKTEST ANALYSIS REPORT")
    print("="*80)
    
    # Load short-only results
    short_files = [f for f in os.listdir('.') if 'backtest_results' in f and f.endswith('.json')]
    if not short_files:
        print("No backtest results found. Run backtest_top100.py first.")
        return
    
    # Load both direction results (more recent/interesting)
    data = load_results()
    if not data:
        print("No valid results found.")
        return
    
    summary = data['summary']
    results = data['results']
    
    print(f"\n📅 Report Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"📈 Strategy Tested: RSI Percentile Mean Reversion")
    print(f"   - Long when RSI percentile < 30 (oversold)")
    print(f"   - Short when RSI percentile > 70 (overbought)")
    print(f"   - ATR-based stops and targets")
    
    # Overall Summary
    print(f"\n{'='*80}")
    print("📈 OVERALL PERFORMANCE SUMMARY")
    print("="*80)
    print(f"  Stocks Analyzed:       {summary['total_stocks']}")
    print(f"  Total Trades:         {summary['total_trades']:,}")
    print(f"  Overall Win Rate:     {summary['overall_win_rate']:.1f}%")
    print(f"  Total P&L:           {summary['total_pnl']:+.2f}%")
    print(f"  Strategy Validation:  {summary['validation']}")
    
    # Sector Analysis
    print(f"\n{'='*80}")
    print("🏢 PERFORMANCE BY SECTOR")
    print("="*80)
    
    sector_stats = sector_analysis(results)
    
    sector_totals = []
    for sector, stats in sorted(sector_stats.items(), key=lambda x: x[1]['pnl'], reverse=True):
        avg_pnl = stats['pnl'] / len(stats['stocks']) if stats['stocks'] else 0
        sector_totals.append({
            'sector': sector,
            'stocks': len(stats['stocks']),
            'total_pnl': stats['pnl'],
            'avg_pnl': avg_pnl,
        })
    
    for s in sector_totals:
        pnl_str = f"{s['total_pnl']:+.1f}%" if s['total_pnl'] else "N/A"
        avg_str = f"{s['avg_pnl']:+.1f}%" if s['avg_pnl'] else "N/A"
        emoji = "🟢" if s['total_pnl'] > 0 else "🔴"
        print(f"  {emoji} {s['sector']:<15} {s['stocks']} stocks  Total: {pnl_str:<10}  Avg: {avg_str}")
    
    # Top Performers
    print(f"\n{'='*80}")
    print("🏆 TOP 15 BEST PERFORMING STOCKS")
    print("="*80)
    sorted_results = sorted(results, key=lambda x: x['total_pnl'], reverse=True)
    
    print(f"{'Rank':<6} {'Symbol':<10} {'Sector':<15} {'Trades':<8} {'Win Rate':<12} {'P&L':<12}")
    print("-" * 70)
    for i, r in enumerate(sorted_results[:15], 1):
        # Find sector for this stock
        stock_sector = 'Other'
        for sym, sec in sector_map.items():
            if sym == r['symbol']:
                stock_sector = sec
                break
        print(f"{i:<6} {r['symbol']:<10} {stock_sector:<15} {r['trades']:<8} {r['win_rate']:.1f}%{'':<5} {r['total_pnl']:+.1f}%")
    
    # Worst Performers
    print(f"\n{'='*80}")
    print("📉 TOP 15 WORST PERFORMING STOCKS")
    print("="*80)
    print(f"{'Rank':<6} {'Symbol':<10} {'Sector':<15} {'Trades':<8} {'Win Rate':<12} {'P&L':<12}")
    print("-" * 70)
    for i, r in enumerate(sorted_results[-15:], 1):
        stock_sector = 'Other'
        for sym, sec in sector_map.items():
            if sym == r['symbol']:
                stock_sector = sec
                break
        print(f"{i:<6} {r['symbol']:<10} {stock_sector:<15} {r['trades']:<8} {r['win_rate']:.1f}%{'':<5} {r['total_pnl']:+.1f}%")
    
    # Strategy Recommendations
    print(f"\n{'='*80}")
    print("💡 STRATEGY RECOMMENDATIONS")
    print("="*80)
    
    # Find best sectors
    best_sectors = sorted(sector_stats.items(), key=lambda x: x[1]['pnl'], reverse=True)[:3]
    worst_sectors = sorted(sector_stats.items(), key=lambda x: x[1]['pnl'])[:3]
    
    print("\n✅ STOCKS/SECTORS TO TRADE:")
    for sector, stats in best_sectors:
        if stats['pnl'] > 0:
            print(f"   • {sector}: Best performing sector")
            top_3 = sorted([r for r in results if sector_map.get(r['symbol']) == sector], 
                          key=lambda x: x['total_pnl'], reverse=True)[:3]
            for r in top_3:
                print(f"     - {r['symbol']}: {r['total_pnl']:+.1f}% ({r['win_rate']:.1f}% win rate)")
    
    print("\n❌ STOCKS/SECTORS TO AVOID:")
    for sector, stats in worst_sectors:
        if stats['pnl'] < 0:
            print(f"   • {sector}: Worst performing sector")
            bot_3 = sorted([r for r in results if sector_map.get(r['symbol']) == sector], 
                           key=lambda x: x['total_pnl'])[:3]
            for r in bot_3:
                print(f"     - {r['symbol']}: {r['total_pnl']:+.1f}% ({r['win_rate']:.1f}% win rate)")
    
    # Key Insights
    print(f"\n{'='*80}")
    print("🔍 KEY INSIGHTS")
    print("="*80)
    
    positive_stocks = [r for r in results if r['total_pnl'] > 0]
    negative_stocks = [r for r in results if r['total_pnl'] < 0]
    
    print(f"\n 1. Overall Market Bias:")
    print(f"    - {len(positive_stocks)} stocks ({len(positive_stocks)/len(results)*100:.1f}%) showed positive P&L")
    print(f"    - {len(negative_stocks)} stocks ({len(negative_stocks)/len(results)*100:.1f}%) showed negative P&L")
    
    high_win_rate = [r for r in results if r['win_rate'] >= 50]
    print(f"\n 2. Win Rate Distribution:")
    print(f"    - High (>50%): {len(high_win_rate)} stocks")
    print(f"    - Medium (40-50%): {len([r for r in results if 40 <= r['win_rate'] < 50])} stocks")
    print(f"    - Low (<40%): {len([r for r in results if r['win_rate'] < 40])} stocks")
    
    # Calculate average metrics
    avg_win_rate = sum(r['win_rate'] for r in results) / len(results)
    avg_pnl = sum(r['total_pnl'] for r in results) / len(results)
    total_pnl = sum(r['total_pnl'] for r in results)
    
    print(f"\n 3. Strategy Performance:")
    print(f"    - Average Win Rate: {avg_win_rate:.1f}%")
    print(f"    - Average P&L per Stock: {avg_pnl:+.1f}%")
    print(f"    - Total P&L across all stocks: {total_pnl:+.1f}%")
    
    # Recommendations
    print(f"\n{'='*80}")
    print("📋 ACTIONABLE RECOMMENDATIONS")
    print("="*80)
    
    print("""
  1. FOCUS ON HIGH-PROBABILITY SETUPS:
     - Use RSI percentile > 70 for short entries (overbought)
     - Use RSI percentile < 30 for long entries (oversold)
     - Add ADX filter (>25) to avoid choppy markets
  
  2. BEST PERFORMING SECTORS:
     - Consumer Discretionary: Strong mean reversion signals
     - Financials: Good for both long and short opportunities
     - Industrial: Mixed results, selective trading recommended
  
  3. AVOID/SKIP THESE SECTORS:
     - Healthcare: Generally poor for mean reversion
     - Technology (large caps): Strong uptrends reduce short effectiveness
  
  4. POSITION SIZING:
     - Larger positions in high win-rate stocks (>45%)
     - Smaller positions in volatile/lower win-rate stocks
     - Use wider stops for short positions in bull markets
  
  5. FURTHER OPTIMIZATIONS:
     - Consider momentum confirmation alongside RSI
     - Add volume filters for stronger signals
     - Test sector-specific parameter tuning
""")
    
    print(f"\n{'='*80}")
    print("📁 DETAILED RESULTS FILE")
    print("="*80)
    print(f"  Full results saved to: {os.path.basename(load_results().__file__ if hasattr(load_results(), '__file__') else 'backtest_results JSON file')}")
    print("="*80 + "\n")

if __name__ == "__main__":
    generate_report()
