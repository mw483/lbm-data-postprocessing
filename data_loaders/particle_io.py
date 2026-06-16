import numpy as np
import os

def load_source_trajectories(bin_dir, target_source_id, start_step, end_step):
    """
    Reads LBM binary files over time and tracks particles originating 
    from a specific target_source_id.
    Returns a dict: {particle_id: [[x1, y1, z1], [x2, y2, z2], ...]}
    """
    trajectories = {}
    
    for step in range(start_step, end_step + 1):
        idx_path = os.path.join(bin_dir, f"index0-{step}.bin")
        pos_path = os.path.join(bin_dir, f"position0-{step}.bin")
        
        if not os.path.exists(idx_path) or not os.path.exists(pos_path):
            continue
            
        # Load and strip the 1-element byte-header
        indices = np.fromfile(idx_path, dtype=np.int32)[1:]
        # reshape transforms the array into a 3d array. -1 tells numpy to do the math and make as many arrays as required, 3 = 3d arrays [x,y,z].
        positions = np.fromfile(pos_path, dtype=np.float32)[1:].reshape(-1, 3) 
        
        # Filter for particles originating from our target source
        # Since ID = (Source * 10000) + step, floor divide by 10000
        mask = (indices // 10000) == target_source_id
        
        valid_ids = indices[mask]
        valid_pos = positions[mask]
        
        # Append coordinates to the trajectory history
        for p_id, pos in zip(valid_ids, valid_pos):
            if p_id not in trajectories:
                trajectories[p_id] = []
            trajectories[p_id].append(pos)
            
    return trajectories

