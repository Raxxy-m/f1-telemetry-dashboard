# style service

def extract_driver_styles(session, drivers):
    styles = {}

    for drv in drivers:
        drv_info = session.get_driver(drv)
        color = drv_info["TeamColor"]

        if not color.startswith("#"):
            color = f"#{color}"

        styles[drv] = {
            "color": color,
            "label": f"{drv_info['Abbreviation']} ({drv})"
        }

    return styles
