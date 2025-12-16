import os
import numpy as np
import matplotlib.pyplot as plt
import argparse
from collections import defaultdict

def read_data_from_file(file, count, data_lists, seperator):
    lines = open(file,'r').read().split('\n')
    for line in lines:
        line = line.split(seperator)
        if len(line) < count:
            continue
        for i in range(count):
            data_lists[i].append(line[i])

def solution_name_mapping(solution_name):
    """Map solution names to display names"""
    # Remove trailing _0, _1, _2, etc.
    base_name = solution_name
    
    mapping = {
        'MAE_x264_ori': 'WebRTC+x264',
        'MAE_salsify': 'Salsify',
        'MAE_x264_adap': 'MAE'
    }
    
    # Try to match the base name
    for key, value in mapping.items():
        if base_name.startswith(key):
            return value
    
    return base_name  # Return original if no mapping found

def main():
    parser = argparse.ArgumentParser(description='Generate final results from statistics')
    parser.add_argument('--data', type=str, required=True, help='Input data name to filter (e.g., Lecture, Lecture_concat)')
    parser.add_argument('--input', type=str, default='../every_trail_statistics.csv', 
                    help='Input CSV file path')
    parser.add_argument('--output', type=str, default='../parameter_result.log',
                    help='Output log file path')
    parser.add_argument('--fig', type=str, default='../MAE_result.png',
                    help='Output figure path')
    
    args = parser.parse_args()
    
    # Read CSV file
    csv_file = args.input
    if not os.path.exists(csv_file):
        print(f"Error: File {csv_file} not found")
        return
    
    # Parse CSV manually since we need mixed data types
    data_list = []
    bitrate_list = []
    solution_list = []
    avg_vmaf_list = []
    avg_tail_overall_delay_list = []
    
    read_data_from_file(csv_file, 10, [data_list, bitrate_list, solution_list, [], [], [], avg_vmaf_list, [], [], avg_tail_overall_delay_list], ',')
    
    # Group by solution (remove trailing _0, _1, _2, etc.)
    solution_groups = defaultdict(lambda: {'vmaf': [], 'tail_delay': []})
    
    for i, solution in enumerate(solution_list):
        # Filter by args.data
        if data_list[i] != args.data:
            continue
        
        # Extract base solution name (remove trailing _number)
        base_solution = solution.rsplit('_', 1)[0] if solution.rsplit('_', 1)[-1].isdigit() else solution
        
        solution_groups[base_solution]['vmaf'].append(float(avg_vmaf_list[i]))
        solution_groups[base_solution]['tail_delay'].append(float(avg_tail_overall_delay_list[i]))
    
    if not solution_groups:
        print(f"Error: No data found for data name '{args.data}'")
        return
    
    # Calculate averages for each solution
    results = {}
    for solution, values in solution_groups.items():
        avg_vmaf = np.mean(values['vmaf'])
        avg_tail_delay = np.mean(values['tail_delay'])
        results[solution] = {
            'avg_vmaf': avg_vmaf,
            'avg_tail_overall_delay': avg_tail_delay,
            'count': len(values['vmaf'])
        }
    
    # Write results to log file
    output_dir = os.path.dirname(args.output)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir, exist_ok=True)
    
    with open(args.output, 'w') as f:
        f.write(f"Results for data: {args.data}\n")
        f.write("=" * 60 + "\n")
        for solution, result in sorted(results.items()):
            display_name = solution_name_mapping(solution)
            f.write(f"{solution} ({display_name}):\n")
            f.write(f"  Average VMAF: {result['avg_vmaf']:.4f}\n")
            f.write(f"  Average Tail Overall Delay: {result['avg_tail_overall_delay']:.4f}\n")
            f.write(f"  Number of trials: {result['count']}\n")
            f.write("\n")
    
    print(f"Results written to {args.output}")
    
    # Draw plot
    fig_dir = os.path.dirname(args.fig)
    if fig_dir and not os.path.exists(fig_dir):
        os.makedirs(fig_dir, exist_ok=True)
    
    plt.figure(figsize=(6, 4))
    plt.rcParams.update({'font.size': 18})
    
    # Plot each solution
    for solution, result in sorted(results.items()):
        display_name = solution_name_mapping(solution)
        x = result['avg_tail_overall_delay']
        y = result['avg_vmaf']
        
        # Set marker style based on solution type
        if display_name in ['Salsify', 'WebRTC+x264']:
            # Empty circle with black edge
            plt.scatter(x, y, s=100, marker='o', facecolors='none', edgecolors='black', linewidths=2, label=display_name)
            if display_name == 'Salsify':
                plt.annotate(display_name, (x, y), xytext=(5, 5), 
                        textcoords='offset points')
            else:
                plt.annotate(display_name, (x, y), xytext=(-70, -25), 
                        textcoords='offset points')
        elif display_name == 'MAE':
            # Red star
            plt.scatter(x, y, s=200, marker='*', color='red', label=display_name)
            plt.annotate(display_name, (x, y), xytext=(12, -8), 
                    textcoords='offset points', fontweight='bold', color='red')
        else:
            # Default style for other solutions
            plt.scatter(x, y, s=200, alpha=0.7, label=display_name)

    plt.quiver(300, 75, -150, 10,color='gray',angles='xy', scale_units='xy', scale=3, width=0.01)
    plt.text(270, 75.5, 'Better', fontsize=14, rotation= -49, color='gray', fontweight='bold')

    plt.xlabel('Average Tail Overall Delay (ms)')
    plt.ylabel('Average VMAF')
    plt.grid(True, alpha=0.3)
    # plt.legend(loc='best')
    plt.tight_layout()
    
    plt.savefig(args.fig, dpi=300, bbox_inches='tight')
    print(f"Figure saved to {args.fig}")
    plt.close()

if __name__ == '__main__':
    main()
