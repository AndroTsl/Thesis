import numpy as np
import matplotlib.pyplot as plt
from glob import glob
import os

def plot_cdf(results, topology_name, filename_prefix='CDF'):
    """Generate CDF plot for a single topology"""
    plt.figure(figsize=(10, 6))
    k_color_map = {5: 'blue', 6: 'red'}
    
    for data_item in results:
        k = data_item['k']
        sorted_latencies = np.sort(data_item['std_max_latencies'])
        cdf = np.arange(1, len(sorted_latencies)+1) / len(sorted_latencies)
        optimized_latency = data_item['optimized_max']
        line_color = k_color_map.get(k, 'black')

        plt.plot(sorted_latencies, cdf, 
                label=f'Standard K{k}', 
                color=line_color, 
                linestyle='-')
        plt.axvline(optimized_latency, 
                   color=line_color, 
                   linestyle='--',
                   label=f'Optimized K{k}')

    plt.xlabel('Maximum Latency (ms)', fontsize=12)
    plt.ylabel('Cumulative Probability', fontsize=12)
    plt.title(f'{topology_name} - Latency CDF Comparison')
    plt.legend(loc='lower right', fontsize=10)
    plt.grid(True, alpha=0.3)
    plt.ylim(0, 1.0)
    
    # Dynamic axis limits
    all_latencies = [item['optimized_max'] for item in results]
    all_latencies.extend([lat for item in results for lat in item['std_max_latencies']])
    plt.xlim(left=max(0, min(all_latencies)*0.9), 
            right=max(all_latencies)*1.05)

    # Save to plots directory
    os.makedirs('plots', exist_ok=True)
    filename = f'{filename_prefix}_{topology_name}.png'
    plt.savefig(os.path.join('plots', filename), dpi=300, bbox_inches='tight')
    plt.close()

def plot_barchart(results, topology_name, filename_prefix='BarChart'):
    """Generate bar chart for a single topology"""
    plt.figure(figsize=(8, 5))
    k_values = [res['k'] for res in results]
    opt_max = [res['optimized_max'] for res in results]
    std_avg = [res['standard_avg'] for res in results]
    speedups = [std/opt for std, opt in zip(std_avg, opt_max)]
    
    x = np.arange(len(k_values))
    bar_width = 0.3
    
    plt.bar(x - bar_width/2, opt_max, width=bar_width, 
            label='Optimized (Max)', color='green')
    plt.bar(x + bar_width/2, std_avg, width=bar_width, 
            label='Standard (Avg)', color='orange')
    
    # Annotate speedup factors
    for i, speedup in enumerate(speedups):
        plt.text(x[i], max(std_avg[i], opt_max[i]) + 0.1, 
                f'{speedup:.1f}x', ha='center', fontsize=9)
        
    plt.xticks(x, [f'K{k}' for k in k_values])
    plt.xlabel('Number of Controllers')
    plt.ylabel('Latency (ms)')
    plt.title(f'{topology_name} Performance Comparison')
    
    plt.legend(loc='upper center', 
                bbox_to_anchor=(0.5, 0.15),  
                fontsize=10)
   
    plt.grid(axis='y', alpha=0.3)
    plt.tight_layout(rect=[0, 0.1, 1, 1])  # Bottom margin
    
    # Save to plots directory
    os.makedirs('plots', exist_ok=True)
    filename = f'{filename_prefix}_{topology_name}.png'
    plt.savefig(os.path.join('plots', filename), bbox_inches='tight', dpi=300)
    plt.close()

def plot_trial_distribution(standard_latencies: list, k_value: int, topology_name: str, filename: str):
    """Plot distribution of maximum latencies from multiple trials"""
    plt.figure(figsize=(8, 5))
    plt.bar(range(1, len(standard_latencies) + 1), standard_latencies, 
           color='darkblue', width=1.0)
    plt.xlabel('Trial No.')
    plt.ylabel('Maximum latency (ms)')
    plt.title(f'{topology_name} K{k_value} - Latency Distribution')
    
    if len(standard_latencies) == 100:
        plt.xticks([0, 20, 40, 60, 80, 100])
    plt.ylim(bottom=0)
    
    plt.savefig(filename, dpi=300, bbox_inches='tight')
    plt.close()

def process_data():
    """Main processing function"""
    all_results = []
    os.makedirs('plots', exist_ok=True)
    
    # Process all topologies
    for topology in ['Chinanet', 'OS3E']:
        topology_results = []
        for k in [5, 6]:
            try:
                std_file = glob(f'{topology}_K{k}_Standard_*.csv')[0]
                opt_file = glob(f'{topology}_K{k}_Optimized_*.csv')[0]
                
                with open(std_file, 'r') as f:
                    std_latencies = [float(line.strip()) for line in f]
                
                # Generate trial distribution plot for this standard file
                trial_distribution_filename = os.path.join(
                    'plots', 
                    os.path.basename(std_file).replace('.csv', '.png')
                )
                plot_trial_distribution(std_latencies, k, topology, trial_distribution_filename)
                
                with open(opt_file, 'r') as f:
                    opt_latencies = [float(line.strip()) for line in f]
                
                topology_results.append({
                    'topology': topology,
                    'k': k,
                    'std_max_latencies': std_latencies,
                    'optimized_max': np.min(opt_latencies),
                    'standard_avg': np.mean(std_latencies)
                })
                
            except (IndexError, FileNotFoundError):
                print(f"Skipping missing files for {topology} K{k}")
                continue
        
        # Generate CDF and Bar Chart plots if we have results
        if topology_results:
            plot_cdf(topology_results, topology)
            plot_barchart(topology_results, topology)
            all_results.extend(topology_results)
    
    return all_results

if __name__ == '__main__':
    process_data()
