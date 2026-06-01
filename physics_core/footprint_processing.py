import numpy as np

def merge_counts_with_positions(source_map, count_map, target_z=None):
    """
    Combines the coordinate map and count map.
    Optionally filters by z-height for future 3D sensitivity analysis.
    Returns lists of X, Y, Counts for plotting.
    """
    x_coords = []
    y_coords = []
    counts = []
    
    for source_id, count in count_map.items():
        if count > 0 and source_id in source_map:
            pos = source_map[source_id]
            
            # Future-proofing: filter by Z if requested
            if target_z is not None and not np.isclose(pos['z'], target_z):
                continue
                
            x_coords.append(pos['x'])
            y_coords.append(pos['y'])
            counts.append(count)
            
    return np.array(x_coords), np.array(y_coords), np.array(counts)