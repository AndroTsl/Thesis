#!/bin/bash

# File to store results
RESULTS="latency_results.csv"
: > "$RESULTS"  # Clear existing content

for i in {1..100}; do
    echo "--- Iteration $i ---"
    
    # Clean Mininet state
    sudo mn -c
    # Clean ONOS state
    echo "Cleaning ONOS cluster..."
    sudo docker exec -it onos1 bash -c '/root/onos/apache-karaf-4.2.8/bin/client -u karaf -p karaf "wipe-out please"'
    
    sleep 5
    
    # Run Mininet script and capture output
    echo "Starting Mininet..."
    OUTPUT=$(sudo python3 mininet_script.py --file OS3E.graphml --cip 172.20.0.5 172.20.0.6 172.20.0.7 172.20.0.8 172.20.0.9 --cluster-algo standard 2>&1)
    
    # Extract numeric latency value using regex
    MAX_LATENCY=$(echo "$OUTPUT" | grep -oP 'Overall maximum one-way latency is \K\d+\.\d+')
    
    # Save result (only the latency number)
    echo "$MAX_LATENCY" >> "$RESULTS"
    echo "Recorded latency: ${MAX_LATENCY} ms"
    
    # Add delay between iterations
    sleep 5
done

echo "Experiment complete. Results saved to $RESULTS"
