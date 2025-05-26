import xml.etree.ElementTree as ET
import networkx as nx
import numpy as np
from math import radians, sin, cos, sqrt, atan2

#GraphML Parsing
def parse_graphml(file_path):
    """Parse GraphML file and extract nodes with coordinates and edges"""
    tree = ET.parse(file_path)
    root = tree.getroot()
    ns = {'ns': 'http://graphml.graphdrawing.org/xmlns'}
    
    key_map = {}
    for key in root.findall('.//ns:key', ns):
        if key.get('for') == 'node':
            attr_name = key.get('attr.name')
            key_map[attr_name] = key.get('id')
    
    nodes = {}
    for node in root.findall('.//ns:node', ns):
        node_id = node.get('id')
        lat, lon = None, None
        for data in node.findall('ns:data', ns):
            key_id = data.get('key')
            if key_id == key_map.get('Latitude'):
                lat = float(data.text)
            elif key_id == key_map.get('Longitude'):
                lon = float(data.text)
        if lat is not None and lon is not None:
            nodes[node_id] = (lat, lon)

    edges = []
    for edge in root.findall('.//ns:edge', ns):
        src = edge.get('source')
        trg = edge.get('target')
        if src in nodes and trg in nodes:
            edges.append((src, trg))

    return nodes, edges


#Distance Calculations -> Weights -> Calculation of all Shortest Paths
def haversine(lat1, lon1, lat2, lon2):
    """Calculate great-circle distance in kilometers"""
    R = 6371  # Earth radius in km
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    return R * 2 * atan2(sqrt(a), sqrt(1-a))

def create_latency_graph(nodes, edges):
    """Create NetworkX graph with latency edge weights and precompute shortest paths"""
    G = nx.Graph()
    for node_id, coords in nodes.items():
        G.add_node(node_id, pos=coords)
    
    for src, trg in edges:
        lat1, lon1 = nodes[src]
        lat2, lon2 = nodes[trg]
        distance = haversine(lat1, lon1, lat2, lon2)
        latency_ms = (distance / 200000) * 1000  # Convert to milliseconds
        G.add_edge(src, trg, weight=latency_ms)
    
    # Precompute all-pairs shortest path lengths
    precomputed_distances = dict(nx.all_pairs_dijkstra_path_length(G, weight='weight'))
    return G, precomputed_distances


#Clustering Algorithms
def revised_kmeans(G, initial_centers, precomputed_distances):
    """Revised K-means implementation using precomputed distances"""
    nodes = list(G.nodes)
    centers = initial_centers.copy()
    prev_centers = None


    while centers != prev_centers:
        # Assign nodes to nearest center
        clusters = {c: [] for c in centers}
        for node in nodes:
            min_dist = float('inf')
            closest_center = None
            for center in centers:
                dist = precomputed_distances.get(center, {}).get(node, float('inf'))
                if dist < min_dist:
                    min_dist = dist
                    closest_center = center
            if closest_center is not None:
                clusters[closest_center].append(node)
        
        # Update centroids
        new_centers = []
        for cluster in clusters.values():
            if not cluster: continue
            min_sum = float('inf')
            centroid = None
            for node in cluster:
                total_dist = sum(precomputed_distances.get(node, {}).get(n, float('inf')) for n in cluster)
                if total_dist < min_sum:
                    min_sum = total_dist
                    centroid = node
            if centroid is not None:
                new_centers.append(centroid)
        prev_centers = centers.copy()
        centers = new_centers


    return clusters, centers

def find_global_centroid(G, precomputed_distances):
    """Find initial global centroid using minmax criteria with precomputed distances"""
    min_max_latency = float('inf')
    centroid = None
    for node in G.nodes:
        max_latency = 0
        for n in G.nodes:
            dist = precomputed_distances.get(node, {}).get(n, float('inf'))
            if dist > max_latency:
                max_latency = dist
        if max_latency < min_max_latency:
            min_max_latency = max_latency
            centroid = node
    return centroid

def optimized_kmeans(G, k, precomputed_distances):
    """Optimized K-means with progressive partitioning using precomputed distances"""
    initial_center = find_global_centroid(G, precomputed_distances)
    if initial_center is None:
        initial_center = next(iter(G.nodes))  # Fallback
    clusters, centers = revised_kmeans(G, [initial_center], precomputed_distances)
    current_k = 1

    while current_k < k:
        # Find cluster with maximum latency
        max_latency = -1
        target_center = None
        for center in centers:
            cluster_nodes = clusters.get(center, [])
            cluster_latency = max(
                precomputed_distances.get(center, {}).get(n, float('inf')) for n in cluster_nodes
            )
            if cluster_latency > max_latency:
                max_latency = cluster_latency
                target_center = center
        
        if target_center is None:
            break
        
        # Find farthest node in target cluster
        farthest_node = max(
            clusters[target_center],
            key=lambda x: precomputed_distances[target_center].get(x, 0)
        )
        
        new_centers = centers.copy()
        new_centers.append(farthest_node)
        clusters, centers = revised_kmeans(G, new_centers, precomputed_distances)
        current_k = len(centers)

    return clusters, centers

#For Comparison
def standard_kmeans(G, k, precomputed_distances):
    """Standard K-means with random initialization using precomputed distances"""
    
    initial_centers = np.random.choice(
        list(G.nodes()), 
        size=k, 
        replace=False
    ).tolist()
    
    clusters, centers = revised_kmeans(
        G, 
        initial_centers, 
        precomputed_distances
    )
    
    return clusters, centers  
