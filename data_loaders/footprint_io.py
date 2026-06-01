import csv
import numpy as np

def load_source_positions(filepath):
    """
    Reads particle_position.txt.
    Extracts physical X, Y, Z coordinates and the Source ID.
    Source ID is derived by flooring the 8th column by 10000.
    """
    # Initialize empty dictionary to store source IDs and coordinates
    source_map = {}
    with open(filepath, 'r') as f:
        for line in f:
            if not line.strip():
                continue
            cols = line.strip().split()
            
            # Extract absolute coordinates
            x, y, z = float(cols[0]), float(cols[1]), float(cols[2])
            
            # Extract ID from the 8th column (index 7)
            raw_id = int(cols[7])
            source_id = raw_id // 10000  # Floor division
            
            # Store the x, y, z coordinate dictionary for each source ID
            source_map[source_id] = {'x': x, 'y': y, 'z': z}
            
    return source_map

def load_footprint_counts(filepath):
    """
    Reads the 2-row footprint CSV.
    Returns a dictionary mapping Source ID to Particle Count.
    """
    count_map = {}
    with open(filepath, 'r') as f:
        reader = csv.reader(f)
        source_ids = next(reader)
        counts = next(reader)
        
        for s_id, count in zip(source_ids, counts):
            if s_id.strip(): # Ensure it's not empty
                count_map[int(s_id)] = float(count)
                
    return count_map