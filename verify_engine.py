import cv2, os
from cv_engine import analyze_terrain_image

BASE = os.path.dirname(os.path.abspath(__file__))
for name in ['drought_sample1.jpg', 'flood_sample1.jpg', 'flood_sample2.jpg', 'navamesh_logo.png']:
    img = cv2.imread(os.path.join(BASE, 'samples', name))
    res = analyze_terrain_image(img)
    print(f"[{res.get('category')}] {name}")
    print(f"  Status : {res.get('status_message')}")
    print(f"  Metrics: Water={res.get('water_coverage_pct')}%, Drought={res.get('drought_coverage_pct')}%, Sky={res.get('sky_coverage_pct')}%")
    print('-' * 55)
