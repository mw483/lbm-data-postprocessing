import numpy as np
import os

def inspect_binaries(base_dir, time_step=int):
    """
    Probes the LBM binary files to determine their data types and structure.
    """
    index_file = os.path.join(base_dir, f"index0-{time_step}.bin")
    pos_file = os.path.join(base_dir, f"position0-{time_step}.bin")
    sgs_file = os.path.join(base_dir, f"uvw_sgs0-{time_step}.bin")
    uvw_file = os.path.join(base_dir, f"uvw0-{time_step}.bin")
    velocity_file = os.path.join(base_dir, f"velocity0-{time_step}.bin")

    print(f"--- Inspecting Time Step {time_step} ---")

    # 1. Inspect Indices (Try int32 first)
    if os.path.exists(index_file):
        indices = np.fromfile(index_file, dtype=np.int32)[1:]
        print(f"\n[Index File]: Found {len(indices)} items (assuming int32).")
        print(f"First 10 IDs: {indices[:10]}")
    else:
        print(f"Could not find {index_file}")

    # 2. Inspect Positions (Try float32 first)
    if os.path.exists(pos_file):
        positions = np.fromfile(pos_file, dtype=np.float32)[1:]
        print(f"\n[Position File]: Found {len(positions)} floats (assuming float32).")
        
        # If interleaved (X,Y,Z, X,Y,Z), the number of floats should be exactly 3x the number of indices
        if len(positions) == (len(indices) * 3):
            print("Structure looks like Interleaved (X, Y, Z).")
            reshaped_pos = positions.reshape(-1, 3)
            print("First 3 coordinates (X, Y, Z):")
            print(reshaped_pos[:3])
        else:
            print("WARNING: Float count does not equal 3x Index count -3. Might be float64 or planar.")

    # 3. Inspect SGS Velocities (Try float32 first)
    if os.path.exists(pos_file):
        sgs_velocities = np.fromfile(sgs_file, dtype=np.float32)[1:]
        print(f"\n[SGS Velocity File]: Found {len(sgs_velocities)} floats (assuming float32).")
        
        # If interleaved (X,Y,Z, X,Y,Z), the number of floats should be exactly 3x the number of indices
        if len(sgs_velocities) == (len(indices) * 3):
            print("Structure looks like Interleaved (u_sgs, v_sgs, w_sgs).")
            reshaped_sgs = sgs_velocities.reshape(-1, 3)
            print("First 3 velocities (u_sgs, v_sgs, w_sgs):")
            print(reshaped_sgs[:3])
        else:
            print("WARNING: Float count does not equal 3x Index count - 3. Might be float64 or planar.")
    
    # 4. Inspect GS Velocities (Try float32 first)
    if os.path.exists(pos_file):
        gs_velocities = np.fromfile(uvw_file, dtype=np.float32)[1:]
        print(f"\n[ GS Velocity File]: Found {len(gs_velocities)} floats (assuming float32).")
        
        # If interleaved (X,Y,Z, X,Y,Z), the number of floats should be exactly 3x the number of indices
        if len(gs_velocities) == (len(indices) * 3):
            print("Structure looks like Interleaved (u, v, w).")
            reshaped_gs = gs_velocities.reshape(-1, 3)
            print("First 3 velocities (u, v, w):")
            print(reshaped_gs[:3])
        else:
            print("WARNING: Float count does not equal 3x Index count - 3. Might be float64 or planar.")
    
    # 4. Inspect Velocities (Try float32 first)
    if os.path.exists(pos_file):
        velocities = np.fromfile(velocity_file, dtype=np.float32)[1:]
        print(f"\n[Velocity File]: Found {len(velocities)} floats (assuming float32).")
        
        # If interleaved (X,Y,Z, X,Y,Z), the number of floats should be exactly 3x the number of indices
        if len(velocities) == (len(indices) * 3):
            print("Structure looks like Interleaved (u, v, w).")
            reshaped_vel = velocities.reshape(-1, 3)
            print("First 3 velocities (u_tot, v_tot, w_tot):")
            print(reshaped_vel[:3])
        else:
            print("WARNING: Float count does not equal 3x Index count - 3. Might be float64 or planar.")

    else:
        print(f"Could not find {pos_file}")

if __name__ == "__main__":
    # Update this path to where your .bin files are stored
    bin_dir = r"Z:\20260527_particle_flat_3072"
    inspect_binaries(bin_dir, time_step=1800)