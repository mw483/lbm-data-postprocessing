import numpy as np
import os
import polars as pl

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


def load_exact_particle_trajectories(bin_dir, target_particle_ids, start_step, end_step, max_ranks=8):
    """
    Reads LBM binary files over time across ALL available ranks and tracks ONLY specific Particle IDs.
    Returns a dict: {particle_id: [[x1, y1, z1], [x2, y2, z2], ...]}
    """
    trajectories = {p_id: [] for p_id in target_particle_ids}
    
    # Convert to a NumPy array for ultra-fast masking
    target_array = np.array(list(target_particle_ids), dtype=np.int32)
    
    files_found = 0
    
    for step in range(start_step, end_step + 1):
        
        # Inner loop: Check every possible rank for this timestep
        for rank in range(max_ranks):
            idx_path = os.path.join(bin_dir, f"index{rank}-{step}.bin")
            pos_path = os.path.join(bin_dir, f"position{rank}-{step}.bin")
            
            # If this rank file doesn't exist, just skip to the next rank
            if not os.path.exists(idx_path) or not os.path.exists(pos_path):
                continue
                
            files_found += 1
            
            # Load and strip the 1-element byte-header
            indices = np.fromfile(idx_path, dtype=np.int32)[1:]
            positions = np.fromfile(pos_path, dtype=np.float32)[1:].reshape(-1, 3)
            
            # Fast NumPy filtering
            mask = np.isin(indices, target_array)
            
            valid_ids = indices[mask]
            valid_pos = positions[mask]
            
            # Append coordinates to the trajectory history
            for p_id, pos in zip(valid_ids, valid_pos):
                trajectories[p_id].append(pos)
                
    print(f"\n[DEBUG] Successfully opened and scanned {files_found} binary files across all ranks.")
    
    if files_found > 0:
        matched_points = sum(len(v) for v in trajectories.values())
        print(f"[DEBUG] Total coordinate points extracted across all files: {matched_points}")
        
    return trajectories


def extract_hit_list_from_time_capsule(filepath, target_sensor_id):
    """
    Parses the C++ sensor_hit_ids.txt file to extract the successful Particle IDs.
    """
    hit_list = set()
    with open(filepath, 'r') as f:
        for line in f:
            parts = line.split()
            if len(parts) == 6 and int(parts[0]) == target_sensor_id:
                hit_list.add(int(parts[5])) # The 6th column is the Particle ID
    return hit_list


def load_streamed_trajectories(csv_path, time_capsule_path, target_sensor_id):
    """
    Rapidly parses a massive trajectory CSV using Polars, filters it using the Time Capsule, 
    and returns a dictionary of chronological coordinates for a specific sensor.
    """
    print(f"Loading Time Capsule to find particles for Sensor {target_sensor_id}...")

    # 1. Load the time capsule (particle-sensor hit list)
    capsule_df = pl.read_csv(
        time_capsule_path,
        separator=" ",
        has_header=False,
        new_columns=["Sensor_ID", "SX", "SY", "SZ", "Source_ID", "Particle_ID"]
    )

    # Extract just the unique particle IDs that hit the target sensors
    target_ids = capsule_df.filter(pl.col("Sensor_ID") == target_sensor_id)["Particle_ID"].unique()

    if len(target_ids) == 0:
        print(f"[ERROR] No particles found for Sensor {target_sensor_id} in the Time Capsule.")
        return {}

    print(f"Found {len(target_ids)} particles. Sweeping the Trajectory database...")

    # 2. Load the trajectory file
    # Polars reads the big file quickly
    traj_df = pl.read_csv(
        csv_path,
        has_header=False,
        new_columns=["Time", "Particle_ID", "X", "Y", "Z"]
    )

    # 3. Filter the millions of rows down to only the target particles
    filtered_df = traj_df.filter(pl.col("Particle_ID").is_in(target_ids))

    # 4. Sort by time
    # Important
    sorted_df = filtered_df.sort(["Particle_ID", "Time"])

    # Group by particle ID and assemble into lists
    grouped = sorted_df.group_by("Particle_ID").agg([
        pl.col("X"), pl.col("Y"), pl.col("Z")
    ]
    )

    # 6. Convert back to the exact dictionary format for the PyVista script
    trajectories = {}
    for row in grouped.iter_rows():
        p_id, x_list, y_list, z_list = row
        # Stack X, Y, Z lists into a 2D numpy array of coordinates
        trajectories[p_id] = np.column_stack((x_list, y_list, z_list))

    print(f"[SUCCESS] Filtered dataset ready for PyVista: {len(trajectories)} pathways.")
    return trajectories