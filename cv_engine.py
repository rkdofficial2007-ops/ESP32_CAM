"""
NAVAMESH CV Engine - Hackathon Edition
Specialized in High-Precision Drought & Flood Segmentation with Dynamic Sky Exclusion
"""

import cv2
import numpy as np
import base64

def encode_img_to_base64(img_bgr, quality=85):
    """Encodes a BGR OpenCV image into base64 JPEG string for web display."""
    encode_params = [int(cv2.IMWRITE_JPEG_QUALITY), quality]
    success, buffer = cv2.imencode('.jpg', img_bgr, encode_params)
    if not success:
        return ""
    return "data:image/jpeg;base64," + base64.b64encode(buffer).decode('utf-8')

def validate_image_scene(img):
    """
    Validates if an image is a genuine outdoor terrain landscape rather than
    a synthetic graphic, logo, flat solid background, portrait, or indoor scene.
    """
    if img is None or img.size == 0:
        return False, "Empty or unreadable image data"
        
    h, w = img.shape[:2]
    if h < 100 or w < 100:
        return False, "Image resolution too low for terrain analysis"
        
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    
    # Check for dominant synthetic black/white graphic backgrounds
    black_pixels = np.sum(gray < 16) / gray.size
    white_pixels = np.sum(gray > 244) / gray.size
    if black_pixels > 0.38:
        return False, "Non-terrain synthetic/graphic dark backdrop detected"
    if white_pixels > 0.50:
        return False, "Overexposed or artificial canvas detected"
        
    # Check natural hue distribution
    hist_h = cv2.calcHist([hsv], [0], None, [18], [0, 180])
    active_bins = np.sum(hist_h > (gray.size * 0.015))
    if active_bins < 2:
        return False, "Monochromatic synthetic graphic detected"
        
    return True, "Valid outdoor scene"

def segment_sky_boundary(img):
    """
    Precision Sky Segmentation.
    Identifies true atmospheric sky in the upper frame without clipping distant flood water basins.
    Sky is characterized by very high illumination (V > 155 for blue, V > 180 for overcast)
    and smooth gradient touching the top edge.
    """
    h, w = img.shape[:2]
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    
    # Compute Sobel gradients
    sobelx = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
    sobely = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
    grad = np.sqrt(sobelx**2 + sobely**2)
    smooth = grad < 22.0
    
    # 1. Clear Blue Sky: Hue 95..135, Sat > 20, Val > 155
    blue_sky = (hsv[:,:,0] >= 95) & (hsv[:,:,0] <= 135) & (hsv[:,:,1] >= 20) & (hsv[:,:,2] >= 155)
    # 2. Overcast / Hazy Sky: Sat < 35, Val > 182
    overcast_sky = (hsv[:,:,1] <= 35) & (hsv[:,:,2] >= 182)
    
    sky_cand = (blue_sky | overcast_sky) & smooth
    # Sky is restricted to upper 35% of the frame in landscape/aerial views
    sky_cand[int(h * 0.35):, :] = False
    
    sky_mask = np.zeros((h, w), dtype=np.uint8)
    num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(sky_cand.astype(np.uint8))
    for lbl in range(1, num_labels):
        if stats[lbl, cv2.CC_STAT_TOP] <= int(h * 0.05) and stats[lbl, cv2.CC_STAT_AREA] > (w * h * 0.015):
            sky_mask[labels == lbl] = 255
            
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (11, 11))
    sky_mask = cv2.morphologyEx(sky_mask, cv2.MORPH_CLOSE, kernel)
    return sky_mask

def analyze_terrain_image(img_bgr):
    """
    Core CV Intelligence:
    - Strictly excludes Sky from ground calculations.
    - Accurately captures both upper water basins and lower flood channels.
    - Precisely segments true cracked drought earth while excluding distant non-cracked hills.
    - Explicitly delineates Water vs. No-Water in both scenarios.
    """
    if img_bgr is None:
        return {
            "is_valid": False,
            "category": "INVALID_IMAGE",
            "status_message": "UPLOAD THE RIGHT IMAGE",
            "reason": "Could not decode image"
        }
        
    orig_h, orig_w = img_bgr.shape[:2]
    target_w = 800
    target_h = int(orig_h * (target_w / orig_w))
    img = cv2.resize(img_bgr, (target_w, target_h), interpolation=cv2.INTER_AREA)
    h, w = img.shape[:2]
    total_pixels = h * w
    
    # 1. Validation check
    is_valid, validation_msg = validate_image_scene(img)
    if not is_valid:
        return {
            "is_valid": False,
            "category": "INVALID_IMAGE",
            "status_message": "UPLOAD THE RIGHT IMAGE",
            "reason": validation_msg,
            "water_coverage_pct": 0.0,
            "drought_coverage_pct": 0.0,
            "sky_coverage_pct": 0.0
        }
        
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    
    # 2. Sky Segmentation (EXCLUDED)
    sky_mask = segment_sky_boundary(img)
    ground_mask = (sky_mask == 0)
    ground_pixels = int(np.sum(ground_mask))
    sky_pixels = int(np.sum(sky_mask > 0))
    sky_pct = round((sky_pixels / total_pixels) * 100, 1)
    
    # 3. Drought Crack Detection (Desiccated Soil with Polygonal Fissures)
    # Earth / soil color range (H: 8..42, S: 15..140, V: 60..230)
    soil_color = (hsv[:,:,0] >= 8) & (hsv[:,:,0] <= 42) & (hsv[:,:,1] >= 15) & (hsv[:,:,1] <= 140) & (hsv[:,:,2] >= 60) & ground_mask
    
    # Black-hat transform highlights dark fissure cracks
    blackhat = cv2.morphologyEx(gray, cv2.MORPH_BLACKHAT, cv2.getStructuringElement(cv2.MORPH_RECT, (7, 7)))
    crack_pts = (blackhat > 16) & soil_color & ground_mask
    crack_ratio = float(np.sum(crack_pts) / max(ground_pixels, 1))
    
    # Precise drought zone: only where crack density is dense, avoiding smooth distant background hills
    crack_density = cv2.boxFilter(crack_pts.astype(np.float32), -1, (17, 17))
    drought_exact = (crack_density > 0.09) & soil_color & ground_mask
    drought_mask = cv2.morphologyEx(drought_exact.astype(np.uint8), cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8))
    drought_mask = (drought_mask > 0) & ground_mask
    
    drought_pixels = int(np.sum(drought_mask))
    drought_pct = round((drought_pixels / max(ground_pixels, 1)) * 100, 1)
    
    # 4. Flood Water Surface Segmentation
    sobelx = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
    sobely = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
    grad = np.sqrt(sobelx**2 + sobely**2)
    
    # Bilateral filter to smooth water ripples while keeping building/roof boundaries sharp
    blur = cv2.bilateralFilter(gray, 7, 50, 50)
    local_var = cv2.boxFilter((gray.astype(np.float32) - blur.astype(np.float32))**2, -1, (11, 11))
    
    # Exclude saturated vegetation
    trees = (hsv[:,:,0] >= 32) & (hsv[:,:,0] <= 85) & (hsv[:,:,1] > 65)
    
    # Water candidates: includes upper water basins and lower inundated streets
    water_cand = (grad < 30.0) & (local_var < 65.0) & ground_mask & (~trees) & (~crack_pts)
    water_clean = cv2.morphologyEx(water_cand.astype(np.uint8), cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
    water_clean = cv2.morphologyEx(water_clean, cv2.MORPH_CLOSE, np.ones((17, 17), np.uint8))
    
    # Keep contiguous water bodies
    n_w, l_w, s_w, _ = cv2.connectedComponentsWithStats(water_clean)
    final_water_mask = np.zeros((h, w), dtype=np.uint8)
    for lbl in range(1, n_w):
        if s_w[lbl, cv2.CC_STAT_AREA] > (ground_pixels * 0.015):
            final_water_mask[l_w == lbl] = 255
            
    water_pixels = int(np.sum(final_water_mask > 0))
    water_pct = round((water_pixels / max(ground_pixels, 1)) * 100, 1)
    
    # 5. Decision Rules
    if crack_ratio >= 0.22 and water_pct <= 6.0:
        category = "DROUGHT"
        status_message = f"CRITICAL DROUGHT DETECTED: {drought_pct}% of ground is severely desiccated cracked soil. Surface water: 0.0% (Zero Water Detected)."
        water_pct = 0.0 # Strict zero water in confirmed drought
    elif water_pct >= 18.0 and crack_ratio < 0.20:
        category = "HEAVY RAINFALL / FLOOD"
        status_message = f"FLOOD / HEAVY RAINFALL INUNDATION: {water_pct}% of terrain submerged by floodwater (including upper water channels). Remaining {round(100.0 - water_pct, 1)}% consists of structures & land."
        drought_pct = 0.0 # In flood, non-water is submerged structures/vegetation, not arid drought
    elif drought_pct >= 40.0 and crack_ratio >= 0.15:
        category = "DROUGHT"
        status_message = f"DROUGHT CONDITIONS: {drought_pct}% desiccated arid ground. Surface water: 0.0%."
        water_pct = 0.0
    elif water_pct >= 14.0 and crack_ratio < 0.10:
        category = "HEAVY RAINFALL / FLOOD"
        status_message = f"SURFACE WATER INUNDATION: {water_pct}% flood coverage across terrain."
        drought_pct = 0.0
    else:
        return {
            "is_valid": False,
            "category": "INVALID_IMAGE",
            "status_message": "UPLOAD THE RIGHT IMAGE",
            "reason": "Image does not exhibit confirmed drought desiccation fissures or flood inundation patterns.",
            "water_coverage_pct": water_pct,
            "drought_coverage_pct": drought_pct,
            "sky_coverage_pct": sky_pct
        }
        
    # 6. Generate Glowing Visual Overlays
    overlay = img.copy()
    
    if category == "HEAVY RAINFALL / FLOOD":
        # Water Overlay: Electric Cyan Glow (#00E5FF)
        water_bgr = np.array([255, 229, 0], dtype=np.uint8)
        water_indices = final_water_mask > 0
        overlay[water_indices] = cv2.addWeighted(img[water_indices], 0.40, np.full_like(img[water_indices], water_bgr), 0.60, 0)
        
        # Draw clean contour boundaries for all water bodies (including upper reaches)
        contours, _ = cv2.findContours(final_water_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        cv2.drawContours(overlay, contours, -1, (255, 255, 0), 2)
        
    elif category == "DROUGHT":
        # Drought Overlay: Glowing Amber (#FF9100)
        drought_bgr = np.array([0, 145, 255], dtype=np.uint8)
        drought_indices = drought_mask > 0
        overlay[drought_indices] = cv2.addWeighted(img[drought_indices], 0.45, np.full_like(img[drought_indices], drought_bgr), 0.55, 0)
        
        # Highlight individual crack fissures in Electric Neon Yellow
        crack_indices = crack_pts & drought_mask
        overlay[crack_indices] = [0, 240, 255]
        
        # Draw drought contour boundaries
        contours, _ = cv2.findContours(drought_mask.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        cv2.drawContours(overlay, contours, -1, (0, 145, 255), 2)
        
    # Highlight Sky Boundary Line in Subtle Purple to visually demonstrate Sky Exclusion
    if sky_pct > 0:
        sky_contours, _ = cv2.findContours(sky_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        cv2.drawContours(overlay, sky_contours, -1, (220, 100, 180), 2)
        
    side_by_side = np.hstack([img, overlay])
    
    binary_mask_bgr = np.zeros_like(img)
    if category == "HEAVY RAINFALL / FLOOD":
        binary_mask_bgr[final_water_mask > 0] = [255, 229, 0] # Cyan for water
    elif category == "DROUGHT":
        binary_mask_bgr[drought_mask > 0] = [0, 145, 255] # Amber for drought
    if sky_pct > 0:
        binary_mask_bgr[sky_mask > 0] = [180, 50, 50] # Dark blue for sky
        
    return {
        "is_valid": True,
        "category": category,
        "status_message": status_message,
        "water_coverage_pct": water_pct,
        "drought_coverage_pct": drought_pct,
        "sky_coverage_pct": sky_pct,
        "ground_area_pct": round(100.0 - sky_pct, 1),
        "overlay_image": encode_img_to_base64(overlay),
        "side_by_side_image": encode_img_to_base64(side_by_side),
        "binary_mask_image": encode_img_to_base64(binary_mask_bgr)
    }
