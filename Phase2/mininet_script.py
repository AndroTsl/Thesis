#!/usr/bin/env python
from mininet.net import Mininet
from mininet.node import Controller, RemoteController, OVSSwitch
from mininet.link import TCLink
from mininet.cli import CLI
from mininet.log import setLogLevel
import argparse
from clustering_module import parse_graphml, create_latency_graph, optimized_kmeans, standard_kmeans
import networkx as nx
import time

class GraphMLTopology:
    def __init__(self, graphml_file, controllers, cluster_algo):
        self.nodes = {}
        self.edges = []
        self.precomputed_distances = {}
        self.graphml_file = graphml_file
        self.controllers = controllers
        self.cluster_algo = cluster_algo
        self.clusters = {}
        self.centers = []
        self._parse_and_process_graphml()

    def _parse_and_process_graphml(self):
        """Parse GraphML and compute latency matrix"""
        self.nodes, self.edges = parse_graphml(self.graphml_file)
        G, self.precomputed_distances = create_latency_graph(self.nodes, self.edges)
        self.switches = list(self.nodes.keys())

    def build_mininet_topology(self):
        net = Mininet(switch=OVSSwitch, controller=None, link=TCLink)
        
        # Add multiple remote controllers
        controllers = []
        for i, (ip, port) in enumerate(self.controllers):
            ctrl = net.addController(f'c{i}', 
                                   controller=RemoteController,
                                   ip=ip,
                                   port=port,
                                   protocol='tcp')
            controllers.append(ctrl)
        
        # Create switches with OpenFlow 1.3
        switches = {}
        for sw in self.switches:
            switches[sw] = net.addSwitch(f's{sw}', dpid=sw.zfill(16),
                                       protocols='OpenFlow13')
        
        # Create hosts and connect to switches
        for sw in self.switches:
            host = net.addHost(f'h{sw}', ip=f'10.0.0.{sw}/24')
            net.addLink(host, switches[sw])
        
        # Create switch-to-switch links with geographic latency
        for src, dst in self.edges:
            try:
                # Get bidirectional latency (max of both directions)
                latency = max(
                    self.precomputed_distances[src][dst],
                    self.precomputed_distances[dst][src]
                )
            except KeyError:
                print(f"Warning: Missing latency for {src}-{dst}, using 1ms")
                latency = 1  # fallback
                
            net.addLink(switches[src], switches[dst], 
                       delay=f'{latency}ms',
                       cls=TCLink)
        
        net.build()
        
        # Perform clustering with selected algorithm
        G = nx.Graph()
        G.add_nodes_from(self.switches)
        G.add_edges_from(self.edges)
        k = len(controllers)
        
        if self.cluster_algo == 'optimized':
            clusters, centers = optimized_kmeans(G, k, self.precomputed_distances)
        else:
            clusters, centers = standard_kmeans(G, k, self.precomputed_distances)
        
        # Assign switches to controllers
        cluster_centers = sorted(centers)
        switch_controller_map = {}
        for i, center in enumerate(cluster_centers):
            for switch in clusters.get(center, []):
                switch_controller_map[switch] = i
        
        # Start controllers
        for ctrl in controllers:
            ctrl.start()
        
        # Connect switches to assigned controllers
        for sw_id, sw in switches.items():
            controller_idx = switch_controller_map.get(sw_id, 0)
            sw.start([controllers[controller_idx]])
        
        # Save clusters and centers for latency measurement
        self.clusters = clusters
        self.centers = centers
        
        return net

def measure_mininet_max_latency(net, clusters_map, controller_centers_list):
    max_one_way_latency = 0.0
    
    for center_sw_id in controller_centers_list:
        center_host = net.get(f'h{center_sw_id}')
        members = clusters_map.get(center_sw_id, [])
        
        for member_sw_id in members:
            if member_sw_id == center_sw_id:
                continue
            
            member_host = net.get(f'h{member_sw_id}')
            
            # Warm-up: 10 pings with reduced interval (output visible)
            print(f"Warm-up pinging h{member_sw_id} -> h{center_sw_id}...")
            warm_up_result = member_host.cmd(f'ping -c 10 -i 0.02 -W 0.3 10.0.0.{center_sw_id}')
            print(warm_up_result)  # Show warm-up results
            
            # Measure: 50 pings with reduced interval (output visible)
            print(f"Measuring h{member_sw_id} -> h{center_sw_id}...")
            ping_cmd = f'ping -c 50 -i 0.02 -W 0.3 10.0.0.{center_sw_id}'
            result = member_host.cmd(ping_cmd)
            print(result)  # Show measurement results
            
            rtt_times = []
            for line in result.split('\n'):
                if 'time=' in line:
                    time_str = line.split('time=')[1].split(' ')[0]
                    rtt_times.append(float(time_str))
            
            if len(rtt_times) >= 40:  # Require at least 40 successful pings
                # Discard first 10, average last 40 (adjust based on your needs)
                avg_rtt = sum(rtt_times[10:]) / len(rtt_times[10:])
                one_way = avg_rtt / 2
                max_one_way_latency = max(max_one_way_latency, one_way)
                print(f"Processed: avg_rtt={avg_rtt:.2f}ms, one_way={one_way:.2f}ms")
    
    return max_one_way_latency

def parse_arguments():
    parser = argparse.ArgumentParser(description='Mininet Topology Builder from GraphML')
    parser.add_argument('--file', required=True, help='Path to GraphML file')
    parser.add_argument('--cip', nargs='+', default=['127.0.0.1'],
                       help='Controller IP addresses (space-separated)')
    parser.add_argument('--cport', nargs='+', default=['6653'],
                       help='Controller ports (space-separated)')
    parser.add_argument('--cluster-algo', choices=['optimized', 'standard'], default='optimized',
                       help='Clustering algorithm to use (optimized/standard)')
    return parser.parse_args()

def process_controller_args(args):
    """Match IPs and ports with fallback to default port"""
    controllers = []
    default_port = 6653
    
    if len(args.cport) < len(args.cip):
        args.cport += [args.cport[-1]] * (len(args.cip) - len(args.cport))
    
    for i, ip in enumerate(args.cip):
        try:
            port = int(args.cport[i]) if i < len(args.cport) else default_port
        except (IndexError, ValueError):
            port = default_port
        controllers.append((ip, port))
    
    return controllers    

if __name__ == '__main__':
    setLogLevel('info')
    args = parse_arguments()
    
    # Process controller arguments
    controllers = process_controller_args(args)
    
    # Create and start network
    topology = GraphMLTopology(args.file, controllers, args.cluster_algo)
    net = topology.build_mininet_topology()
    
    print("\nNetwork configuration:")
    print(f"GraphML file: {args.file}")
    print(f"Controllers: {controllers}")
    print(f"Clustering algorithm: {args.cluster_algo}")
    print(f"Geographic delays enabled: Yes")
    print("Network ready!")

    # Allow time for warm-up and prime ARP tables
    print("Waiting 15 seconds for network stabilization...")
    time.sleep(15)
    
    #print("Priming ARP tables with pingAll...")
    #net.pingAll()
    
    # Measure maximum latency
    print("\nMeasuring cluster latencies...")
    max_latency = measure_mininet_max_latency(net, topology.clusters, topology.centers)
    print(f"\n=== RESULT: Overall maximum one-way latency is {max_latency:.2f} ms ===")
    
    #CLI(net)
    net.stop()
