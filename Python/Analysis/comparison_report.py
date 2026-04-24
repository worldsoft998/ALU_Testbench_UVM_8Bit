#!/usr/bin/env python3
"""
Comparison Analysis Script
Analyzes and compares baseline vs AI-assisted simulation results

Author: AI Assistant
Date: 2026-04-24
"""

import argparse
import json
import re
import sys
from dataclasses import dataclass
from typing import Dict, Any, List, Optional
from datetime import datetime


@dataclass
class SimulationResult:
    """Container for simulation results"""
    mode: str  # 'baseline' or 'ai'
    transactions: int
    coverage: float
    duration: float  # seconds
    algorithm: str
    bugs_found: int
    efficiency: float  # transactions per second
    coverage_rate: float  # coverage per transaction


class ComparisonAnalyzer:
    """Analyzes comparison between baseline and AI simulations"""
    
    def __init__(self):
        self.baseline_result: Optional[SimulationResult] = None
        self.ai_result: Optional[SimulationResult] = None
        self.comparison: Dict[str, Any] = {}
    
    def load_from_log(self, log_path: str, mode: str) -> SimulationResult:
        """Load simulation results from log file"""
        result = SimulationResult(
            mode=mode,
            transactions=0,
            coverage=0.0,
            duration=0.0,
            algorithm='random' if mode == 'baseline' else 'unknown',
            bugs_found=0,
            efficiency=0.0,
            coverage_rate=0.0
        )
        
        try:
            with open(log_path, 'r') as f:
                content = f.read()
            
            # Parse transactions
            txn_match = re.search(r'Transactions:\s*(\d+)', content)
            if txn_match:
                result.transactions = int(txn_match.group(1))
            
            # Parse coverage
            cov_match = re.search(r'Coverage:\s*(\d+\.?\d*)%', content)
            if cov_match:
                result.coverage = float(cov_match.group(1)) / 100.0
            
            # Parse algorithm (for AI mode)
            algo_match = re.search(r'Algorithm:\s*(\w+)', content)
            if algo_match:
                result.algorithm = algo_match.group(1)
            
            # Parse duration
            time_match = re.search(r'Time:\s*(\d+\.?\d*)', content)
            if time_match:
                result.duration = float(time_match.group(1))
            
            # Parse bugs
            bug_match = re.search(r'Bugs?\s*Found:\s*(\d+)', content)
            if bug_match:
                result.bugs_found = int(bug_match.group(1))
            
            # Calculate efficiency
            if result.duration > 0:
                result.efficiency = result.transactions / result.duration
            
            # Calculate coverage rate
            if result.transactions > 0:
                result.coverage_rate = result.coverage / result.transactions
            
        except FileNotFoundError:
            print(f"Warning: Log file not found: {log_path}")
        except Exception as e:
            print(f"Warning: Error parsing log: {e}")
        
        return result
    
    def load_from_json(self, json_path: str, mode: str) -> SimulationResult:
        """Load simulation results from JSON file"""
        with open(json_path, 'r') as f:
            data = json.load(f)
        
        return SimulationResult(
            mode=mode,
            transactions=data.get('transactions_completed', 0),
            coverage=data.get('coverage', 0.0),
            duration=data.get('duration', 0.0),
            algorithm=data.get('config', {}).get('algorithm', 'unknown'),
            bugs_found=data.get('bugs_found', 0),
            efficiency=data.get('transactions_per_second', 0.0),
            coverage_rate=data.get('coverage', 0.0) / max(data.get('transactions_completed', 1), 1)
        )
    
    def set_results(self, baseline: SimulationResult, ai: SimulationResult):
        """Set baseline and AI results for comparison"""
        self.baseline_result = baseline
        self.ai_result = ai
        self._calculate_comparison()
    
    def _calculate_comparison(self):
        """Calculate comparison metrics"""
        if not self.baseline_result or not self.ai_result:
            return
        
        baseline = self.baseline_result
        ai = self.ai_result
        
        # Transaction reduction
        if baseline.transactions > 0:
            txn_reduction = (baseline.transactions - ai.transactions) / baseline.transactions * 100
        else:
            txn_reduction = 0
        
        # Time reduction
        if baseline.duration > 0:
            time_reduction = (baseline.duration - ai.duration) / baseline.duration * 100
        else:
            time_reduction = 0
        
        # Coverage improvement
        coverage_delta = ai.coverage - baseline.coverage
        
        # Efficiency improvement
        if baseline.efficiency > 0:
            efficiency_improvement = (ai.efficiency - baseline.efficiency) / baseline.efficiency * 100
        else:
            efficiency_improvement = 0
        
        self.comparison = {
            'transaction_reduction_pct': txn_reduction,
            'time_reduction_pct': time_reduction,
            'coverage_delta': coverage_delta,
            'efficiency_improvement_pct': efficiency_improvement,
            'bug_comparison': {
                'baseline': baseline.bugs_found,
                'ai': ai.bugs_found,
                'delta': ai.bugs_found - baseline.bugs_found
            }
        }
    
    def generate_report(self) -> str:
        """Generate comparison report"""
        if not self.baseline_result or not self.ai_result:
            return "Error: Missing simulation results"
        
        baseline = self.baseline_result
        ai = self.ai_result
        
        report = """
================================================================================
                    ALU VERIFICATION COMPARISON REPORT
================================================================================
Generated: {timestamp}

CONFIGURATION
--------------------------------------------------------------------------------
Testbench: 8-bit ALU with UVM
Transactions: {baseline_txn} (baseline) / {ai_txn} (AI)
Algorithm: {baseline_algo} (baseline) / {ai_algo} (AI)

BASELINE RESULTS (No AI)
--------------------------------------------------------------------------------
Transactions:     {baseline_txn:,}
Coverage:         {baseline_cov:.1%}
Time:             {baseline_time:.2f} seconds
Bugs Found:       {baseline_bugs}
Efficiency:       {baseline_eff:.2f} txn/sec
Coverage Rate:    {baseline_rate:.6f} cov/txn

AI-ASSISTED RESULTS ({ai_algo})
--------------------------------------------------------------------------------
Transactions:     {ai_txn:,}
Coverage:         {ai_cov:.1%}
Time:             {ai_time:.2f} seconds
Bugs Found:       {ai_bugs}
Efficiency:       {ai_eff:.2f} txn/sec
Coverage Rate:    {ai_rate:.6f} cov/txn

PERFORMANCE IMPROVEMENTS
--------------------------------------------------------------------------------
Transaction Reduction:  {txn_reduction:+.1f}%
Time Reduction:        {time_reduction:+.1f}%
Coverage Delta:        {cov_delta:+.1%}
Efficiency Improvement: {eff_improvement:+.1f}%

BUG DETECTION COMPARISON
--------------------------------------------------------------------------------
Baseline Bugs:    {baseline_bugs}
AI Bugs:          {ai_bugs}
Difference:       {bug_delta:+d}

ANALYSIS
--------------------------------------------------------------------------------
{analysis_text}

================================================================================
                              END OF REPORT
================================================================================
""".format(
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            baseline_txn=baseline.transactions,
            ai_txn=ai.transactions,
            baseline_algo=baseline.algorithm,
            ai_algo=ai.algorithm,
            baseline_cov=baseline.coverage,
            ai_cov=ai.coverage,
            baseline_time=baseline.duration,
            ai_time=ai.duration,
            baseline_bugs=baseline.bugs_found,
            ai_bugs=ai.bugs_found,
            baseline_eff=baseline.efficiency,
            ai_eff=ai.efficiency,
            baseline_rate=baseline.coverage_rate,
            ai_rate=ai.coverage_rate,
            txn_reduction=self.comparison.get('transaction_reduction_pct', 0),
            time_reduction=self.comparison.get('time_reduction_pct', 0),
            cov_delta=self.comparison.get('coverage_delta', 0),
            eff_improvement=self.comparison.get('efficiency_improvement_pct', 0),
            bug_delta=self.comparison.get('bug_comparison', {}).get('delta', 0),
            analysis_text=self._generate_analysis()
        )
        
        return report
    
    def _generate_analysis(self) -> str:
        """Generate analysis text based on comparison"""
        analysis = []
        
        txn_red = self.comparison.get('transaction_reduction_pct', 0)
        time_red = self.comparison.get('time_reduction_pct', 0)
        cov_delta = self.comparison.get('coverage_delta', 0)
        bug_delta = self.comparison.get('bug_comparison', {}).get('delta', 0)
        
        if txn_red > 0:
            analysis.append(f"- AI achieved {txn_red:.1f}% fewer transactions to reach coverage target")
        elif txn_red < 0:
            analysis.append(f"- AI required {-txn_red:.1f}% more transactions (may indicate better coverage)")
        else:
            analysis.append("- Both configurations achieved similar transaction counts")
        
        if time_red > 0:
            analysis.append(f"- AI simulation completed {time_red:.1f}% faster")
        elif time_red < 0:
            analysis.append(f"- Baseline was {abs(time_red):.1f}% faster")
        else:
            analysis.append("- No significant time difference observed")
        
        if cov_delta > 0.01:
            analysis.append(f"- AI achieved {cov_delta:.1%} higher coverage")
        elif cov_delta < -0.01:
            analysis.append(f"- Baseline achieved {abs(cov_delta):.1%} higher coverage")
        else:
            analysis.append("- Coverage levels are comparable")
        
        if bug_delta > 0:
            analysis.append(f"- AI discovered {bug_delta} more bugs (indicates better corner case coverage)")
        elif bug_delta < 0:
            analysis.append(f"- Baseline discovered {abs(bug_delta)} more bugs")
        else:
            analysis.append("- Both configurations found similar bugs")
        
        # Summary
        positive_count = sum([
            txn_red > 0,
            time_red > 0,
            cov_delta > 0.01,
            bug_delta > 0
        ])
        
        if positive_count >= 3:
            analysis.append("\nSUMMARY: AI assistance provides significant benefits")
        elif positive_count >= 2:
            analysis.append("\nSUMMARY: AI assistance provides moderate benefits")
        elif positive_count >= 1:
            analysis.append("\nSUMMARY: AI assistance provides marginal benefits")
        else:
            analysis.append("\nSUMMARY: AI assistance did not show significant benefits")
        
        return "\n".join(analysis)
    
    def save_report(self, output_path: str):
        """Save report to file"""
        report = self.generate_report()
        with open(output_path, 'w') as f:
            f.write(report)
        print(f"Report saved to: {output_path}")
    
    def export_json(self, output_path: str):
        """Export comparison data as JSON"""
        data = {
            'timestamp': datetime.now().isoformat(),
            'baseline': {
                'transactions': self.baseline_result.transactions if self.baseline_result else 0,
                'coverage': self.baseline_result.coverage if self.baseline_result else 0,
                'duration': self.baseline_result.duration if self.baseline_result else 0,
                'algorithm': self.baseline_result.algorithm if self.baseline_result else '',
                'bugs_found': self.baseline_result.bugs_found if self.baseline_result else 0,
                'efficiency': self.baseline_result.efficiency if self.baseline_result else 0
            },
            'ai': {
                'transactions': self.ai_result.transactions if self.ai_result else 0,
                'coverage': self.ai_result.coverage if self.ai_result else 0,
                'duration': self.ai_result.duration if self.ai_result else 0,
                'algorithm': self.ai_result.algorithm if self.ai_result else '',
                'bugs_found': self.ai_result.bugs_found if self.ai_result else 0,
                'efficiency': self.ai_result.efficiency if self.ai_result else 0
            },
            'comparison': self.comparison
        }
        
        with open(output_path, 'w') as f:
            json.dump(data, f, indent=2)
        
        print(f"JSON data saved to: {output_path}")


def parse_args():
    parser = argparse.ArgumentParser(
        description='Compare baseline vs AI-assisted ALU verification results'
    )
    parser.add_argument(
        '--baseline',
        type=str,
        help='Baseline simulation log or JSON file'
    )
    parser.add_argument(
        '--ai',
        type=str,
        help='AI-assisted simulation log or JSON file'
    )
    parser.add_argument(
        '--output',
        type=str,
        default='comparison_report.txt',
        help='Output file for report'
    )
    parser.add_argument(
        '--json',
        type=str,
        help='Output file for JSON data'
    )
    parser.add_argument(
        '--format',
        choices=['log', 'json', 'auto'],
        default='auto',
        help='Input file format'
    )
    
    return parser.parse_args()


def main():
    args = parse_args()
    
    analyzer = ComparisonAnalyzer()
    
    # Load baseline results
    if args.baseline:
        if args.format == 'auto':
            fmt = 'json' if args.baseline.endswith('.json') else 'log'
        else:
            fmt = args.format
        
        if fmt == 'json':
            baseline = analyzer.load_from_json(args.baseline, 'baseline')
        else:
            baseline = analyzer.load_from_log(args.baseline, 'baseline')
    
    # Load AI results
    if args.ai:
        if args.format == 'auto':
            fmt = 'json' if args.ai.endswith('.json') else 'log'
        else:
            fmt = args.format
        
        if fmt == 'json':
            ai = analyzer.load_from_json(args.ai, 'ai')
        else:
            ai = analyzer.load_from_log(args.ai, 'ai')
    
    # Set results if both loaded
    if args.baseline and args.ai:
        analyzer.set_results(baseline, ai)
        
        # Generate and save report
        print(analyzer.generate_report())
        
        if args.output:
            analyzer.save_report(args.output)
        
        if args.json:
            analyzer.export_json(args.json)
    else:
        print("Please provide both --baseline and --ai inputs for comparison")


if __name__ == '__main__':
    main()