import cv2
import numpy as np
import math
import time

def cubemap_to_equirect(faces, out_w=2048, out_h=1024):
    """
    Reproject 6 cube faces back into an equirectangular image.
    Faces order: Front (0), Right (1), Back (2), Left (3), Top (4), Bottom (5)
    """
    face_size = faces[0].shape[0]
    u = np.arange(out_w)
    v = np.arange(out_h)
    uu, vv = np.meshgrid(u, v)
    
    theta = (uu / out_w - 0.5) * 2.0 * np.pi
    phi = (0.5 - vv / out_h) * np.pi
    
    rx = np.cos(phi) * np.sin(theta)
    ry = np.sin(phi)
    rz = np.cos(phi) * np.cos(theta)
    
    # Absolute max component determines face
    abs_x = np.abs(rx)
    abs_y = np.abs(ry)
    abs_z = np.abs(rz)
    
    # Output canvas
    channels = faces[0].shape[2] if len(faces[0].shape) == 3 else 1
    if channels > 1:
        out = np.zeros((out_h, out_w, channels), dtype=faces[0].dtype)
    else:
        out = np.zeros((out_h, out_w), dtype=faces[0].dtype)
        
    # Face 0: Front (+Z) -> abs_z is max and rz > 0
    mask_front = (abs_z >= abs_x) & (abs_z >= abs_y) & (rz > 0)
    # Face 1: Right (+X) -> abs_x is max and rx > 0
    mask_right = (abs_x >= abs_y) & (abs_x >= abs_z) & (rx > 0)
    # Face 2: Back (-Z) -> abs_z is max and rz < 0
    mask_back = (abs_z >= abs_x) & (abs_z >= abs_y) & (rz < 0)
    # Face 3: Left (-X) -> abs_x is max and rx < 0
    mask_left = (abs_x >= abs_y) & (abs_x >= abs_z) & (rx < 0)
    # Face 4: Top (+Y) -> abs_y is max and ry > 0
    mask_top = (abs_y >= abs_x) & (abs_y >= abs_z) & (ry > 0)
    # Face 5: Bottom (-Y) -> abs_y is max and ry < 0
    mask_bottom = (abs_y >= abs_x) & (abs_y >= abs_z) & (ry < 0)
    
    face_masks = [mask_front, mask_right, mask_back, mask_left, mask_top, mask_bottom]
    
    # Project coords
    # Front: u_f = rx / rz, v_f = ry / rz
    # Right: u_f = -rz / rx, v_f = ry / rx
    # Back: u_f = -rx / -rz = rx / rz, v_f = ry / -rz
    # Left: u_f = rz / -rx, v_f = ry / -rx
    # Top: u_f = rx / ry, v_f = -rz / ry
    # Bottom: u_f = rx / -ry, v_f = rz / -ry
    
    proj_coords = [
        (rx / np.maximum(rz, 1e-6), ry / np.maximum(rz, 1e-6)),
        (-rz / np.maximum(rx, 1e-6), ry / np.maximum(rx, 1e-6)),
        (-rx / np.maximum(-rz, 1e-6), ry / np.maximum(-rz, 1e-6)),
        (rz / np.maximum(-rx, 1e-6), ry / np.maximum(-rx, 1e-6)),
        (rx / np.maximum(ry, 1e-6), -rz / np.maximum(ry, 1e-6)),
        (rx / np.maximum(-ry, 1e-6), rz / np.maximum(-ry, 1e-6)),
    ]
    
    for f_idx in range(6):
        m = face_masks[f_idx]
        if not np.any(m):
            continue
        cu, cv = proj_coords[f_idx]
        
        # Map from [-1, 1] to pixel [0, face_size - 1]
        px = (cu[m] * (face_size / 2.0) + face_size / 2.0 - 0.5).astype(np.float32)
        py = (face_size / 2.0 - cv[m] * (face_size / 2.0) - 0.5).astype(np.float32)
        
        px = np.clip(px, 0, face_size - 1)
        py = np.clip(py, 0, face_size - 1)
        
        # Remap or bilinear sample
        face = faces[f_idx]
        # Fast nearest/bilinear interpolation
        x0 = np.floor(px).astype(int)
        x1 = np.minimum(x0 + 1, face_size - 1)
        y0 = np.floor(py).astype(int)
        y1 = np.minimum(y0 + 1, face_size - 1)
        
        wx = px - x0
        wy = py - y0
        
        if channels > 1:
            wx = wx[:, np.newaxis]
            wy = wy[:, np.newaxis]
            val = (face[y0, x0] * (1 - wx) * (1 - wy) +
                   face[y0, x1] * wx * (1 - wy) +
                   face[y1, x0] * (1 - wx) * wy +
                   face[y1, x1] * wx * wy)
            out[m] = val.astype(out.dtype)
        else:
            val = (face[y0, x0] * (1 - wx) * (1 - wy) +
                   face[y0, x1] * wx * (1 - wy) +
                   face[y1, x0] * (1 - wx) * wy +
                   face[y1, x1] * wx * wy)
            out[m] = val.astype(out.dtype)
            
    return out

# Load the 6 faces and reconstruct equirect
faces = [cv2.imread(f"exports/spatial/tearoom_audit/cube_face_{name}.jpg") for name in ["front", "right", "back", "left", "top", "bottom"]]
t0 = time.time()
reconstructed = cubemap_to_equirect(faces, out_w=2048, out_h=1024)
print(f"[+] Reconstructed equirectangular frame in {time.time() - t0:.2f}s!")
cv2.imwrite("exports/spatial/tearoom_audit/reconstructed_equirect.jpg", reconstructed)
print("[+] Saved exports/spatial/tearoom_audit/reconstructed_equirect.jpg")
