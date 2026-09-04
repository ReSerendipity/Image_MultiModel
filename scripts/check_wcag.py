"""V6: WCAG AA contrast ratio checker."""


def hex_to_luminance(hex_color: str) -> float:
    hex_color = hex_color.replace("#", "")
    r = int(hex_color[0:2], 16) / 255
    g = int(hex_color[2:4], 16) / 255
    b = int(hex_color[4:6], 16) / 255

    def linearize(c: float) -> float:
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    return 0.2126 * linearize(r) + 0.7152 * linearize(g) + 0.0722 * linearize(b)


def contrast_ratio(fg: str, bg: str) -> float:
    l1 = hex_to_luminance(fg)
    l2 = hex_to_luminance(bg)
    return (max(l1, l2) + 0.05) / (min(l1, l2) + 0.05)


pairs = [
    ("Normal text", "#ececec", "#17171a", 4.5),
    ("White on accent", "#ffffff", "#6b5bb8", 4.5),
    ("Accent on bg", "#8b7bd8", "#17171a", 3.0),
    ("White on btn-primary", "#ffffff", "#7c5fd6", 4.5),
    ("Hint on card", "#9999a0", "#1e1e22", 4.5),
]

print("=== V6: WCAG AA Contrast Check ===")
all_pass = True
for name, fg, bg, threshold in pairs:
    ratio = contrast_ratio(fg, bg)
    passed = ratio >= threshold
    status = "✅ PASS" if passed else "❌ FAIL"
    if not passed:
        all_pass = False
    print(f"  {status} {name}: {ratio:.2f}:1 (need ≥{threshold}:1)  fg={fg} bg={bg}")

print(f"\n  {'All passed ✅' if all_pass else 'Some failed ❌'}")
