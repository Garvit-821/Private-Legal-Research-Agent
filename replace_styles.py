import re

with open("static/styles.css", "r") as f:
    css = f.read()

# 1. Update Buttons to Pill Radius
css = re.sub(r'(\.btn-primary,\s*\.btn-secondary,\s*\.btn-icon,\s*\.btn-send\s*\{[^}]*border-radius:\s*)var\(--radius-xl\)', r'\1var(--radius-pill)', css)
css = re.sub(r'(\.logo-pulse\s*\{[^}]*border-radius:\s*)var\(--radius-xl\)', r'\1var(--radius-pill)', css)

# 2. Update Panels and Cards to radius-lg
css = re.sub(r'(\.metric-card\s*\{[^}]*border-radius:\s*)var\(--radius-xl\)', r'\1var(--radius-lg)', css)
css = re.sub(r'(\.panel-card\s*\{[^}]*border-radius:\s*)var\(--radius-xl\)', r'\1var(--radius-lg)', css)
css = re.sub(r'(\.bubble-content\s*\{[^}]*border-radius:\s*)var\(--radius-xl\)', r'\1var(--radius-lg)', css)
css = re.sub(r'(\.context-doc-pill\s*\{[^}]*border-radius:\s*)var\(--radius-xl\)', r'\1var(--radius-pill)', css)
css = re.sub(r'(\.agent-item\s*\{[^}]*border-radius:\s*)var\(--radius-xl\)', r'\1var(--radius-lg)', css)
css = re.sub(r'(\.whiteboard-note\s*\{[^}]*border-radius:\s*)var\(--radius-xl\)', r'\1var(--radius-md)', css)

# 3. Update Inputs
# input and textarea should be 56px height and radius-md according to DESIGN.md
# We will find chat-input-wrapper and docSearch
css = re.sub(r'(#docSearch\s*\{[^}]*padding:\s*)(0\.45rem 0\.6rem 0\.45rem 1\.85rem)', r'\1 14px 16px 14px 32px', css)

# 4. Remove active/green accents and use primary CTA styling for btn-primary
# btn-primary is white on black, with faint background on hover
css = re.sub(r'(\.btn-primary\s*\{[^}]*background:\s*)var\(--accent-primary\)', r'\1var(--accent-primary)', css) # accent-primary is already white
css = re.sub(r'(\.btn-primary:hover:not\(:disabled\)\s*\{[^}]*background:\s*)var\(--accent-primary-active\)', r'\1var(--accent-primary-active)', css)

# 5. Fix panel header bg
css = re.sub(r'(\.panel-header\s*\{[^}]*background:\s*)#ffffff', r'\1var(--panel-bg)', css)
css = re.sub(r'(\.document-viewer-wrapper\s*\{[^}]*background:\s*)#ffffff', r'\1var(--panel-bg)', css)
css = re.sub(r'(\.chat-interface-wrapper\s*\{[^}]*background:\s*)#ffffff', r'\1var(--panel-bg)', css)
css = re.sub(r'(#docSearch\s*\{[^}]*background:\s*)#ffffff', r'\1var(--bg-main)', css)
css = re.sub(r'(\.modal-card\s*\{[^}]*background:\s*)#ffffff', r'\1var(--panel-bg)', css)
css = re.sub(r'(\.toast-notification\s*\{[^}]*background:\s*)#ffffff', r'\1var(--panel-bg)', css)

with open("static/styles.css", "w") as f:
    f.write(css)

print("Styles updated.")
