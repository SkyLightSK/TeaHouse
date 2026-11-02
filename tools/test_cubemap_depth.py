import cv2
import numpy as np
import math
import time

def equirect_to_cubemap_faces(equirect_img, face_size=768):
    """
    Convert equirectangular image into 6 rectilinear cube faces.
    Faces order: Front (0), Right (1), Back (2), Left (3), Top (4), Bottom (5)
    """
    h_eq, w_eq = equirect_img.shape[:2]
    faces = []
    
    # Grid of coordinates on cube face
    u = (np.arange(face_size) - face_size / 2.0 + 0.5) / (face_size / 2.0)
    v = (face_size / 2.0 - np.arange(face_size) - 0.5) / (face_size / 2.0)
    uu, vv = np.meshgrid(u, v)
    ones = np.ones_like(uu)
    
    # 3D ray directions for each face (X: right, Y: up, Z: forward)
    face_rays = [
        np.stack([uu, vv, ones], axis=-1),    # Front (+Z)
        np.stack([ones, vv, -uu], axis=-1),   # Right (+X)
        np.stack([-uu, vv, -ones], axis=-1),  # Back (-Z)
        np.stack([-ones, vv, uu], axis=-1),   # Left (-X)
        np.stack([uu, ones, -vv], axis=-1),   # Top (+Y)
        np.stack([uu, -ones, vv], axis=-1),   # Bottom (-Y)
    ]
    
    for ray in face_rays:
        norm = np.linalg.norm(ray, axis=-1, keepdims=True)
        unit_ray = ray / norm
        rx, ry, rz = unit_ray[..., 0], unit_ray[..., 1], unit_ray[..., 2]
        
        # Convert to spherical equirectangular coordinates
        theta = np.arctan2(rx, rz) # [-pi, pi]
        phi = np.arcsin(np.clip(ry, -1.0, 1.0)) # [-pi/2, pi/2]
        
        u_eq = (theta / (2.0 * math.pi) + 0.5) * w_eq - 0.5
        v_eq = (0.5 - phi / math.pi) * h_eq - 0.5
        
        map_x = u_eq.astype(np.float32)
        map_y = v_eq.astype(np.float32)
        
        face_img = cv2.remap(equirect_img, map_x, map_y, interpolation=cv2.INTER_LINEAR, borderMode=cv2.BORDER_WRAP)
        faces.append(face_img)
        
    return faces

img = cv2.imread("source/captures/panoramas/terra-incognita-tearoom-2017-11.jpg")
t0 = time.time()
faces = equirect_to_cubemap_faces(img, face_size=768)
print(f"[+] Extracted 6 cube faces in {time.time() - t0:.2f}s!")

for i, name in enumerate(["front", "right", "back", "left", "top", "bottom"]):
    cv2.imwrite(f"exports/spatial/tearoom_audit/cube_face_{name}.jpg", faces[i])
print("[+] Saved all 6 cube faces to exports/spatial/tearoom_audit/")
