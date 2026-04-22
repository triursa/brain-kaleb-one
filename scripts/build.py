#!/usr/bin/env python3
"""
Build script for brain.kaleb.one
Reads personal-note domains from second-brain-vault and generates:
  1. Mission Control dashboard (index.html)
  2. Personal notes viewer (per-domain pages)
  3. App cards for graduated domains (launch links)
Liquid Glass aesthetic, static HTML, no JS framework.
"""

import os
import re
import yaml
import json
from pathlib import Path
from string import Template
from datetime import datetime

VAULT_DIR = os.environ.get("VAULT_DIR", "/tmp/second-brain-vault")
OUTPUT_DIR = os.environ.get("OUTPUT_DIR", "/tmp/brain-site")
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_DIR = os.path.join(os.path.dirname(SCRIPT_DIR), "templates")

# ── Domain Configuration ──────────────────────────────────────────────────

PERSONAL_DOMAINS = {
    "health":     {"icon": "💪", "color": "#3b6d11", "desc": "Health goals, gout/fatty liver tracking, vitals"},
    "household":  {"icon": "🏠", "color": "#185fa5", "desc": "Family logistics, contacts, calendar"},
    "novel":      {"icon": "✍️", "color": "#993c1d", "desc": "Writing projects, voice rules, drafts"},
    "finance":    {"icon": "💰", "color": "#7a3f99", "desc": "Home buying, savings, financial planning"},
    "tools":      {"icon": "🔧", "color": "#993556", "desc": "Tool projects, charcreate, image wrangler"},
    "ai-tooling": {"icon": "🤖", "color": "#60a5fa", "desc": "System prompts, skills, infrastructure"},
}

VAULT_SECTIONS = {
    "inbox":   {"icon": "📥", "color": "#a78bfa", "desc": "Unprocessed captures and raw saves"},
    "journal": {"icon": "📓", "color": "#f59e0b", "desc": "Dated session logs and entries"},
    "notes":   {"icon": "📝", "color": "#94a3b8", "desc": "Personal profile, preferences, reference"},
    "maps":    {"icon": "🗺️", "color": "#14b8a6", "desc": "Cross-domain navigation and indexes"},
}

GRADUATED_DOMAINS = {
    "cooking":       {"icon": "🍳", "color": "#f97316", "href": "https://kitchen.kaleb.one", "app": "Kitchen"},
    "entertainment": {"icon": "📺", "color": "#8b5cf6", "href": "https://watch.kaleb.one", "app": "Watch"},
    "books":         {"icon": "📚", "color": "#10b981", "href": "https://read.kaleb.one", "app": "Read"},
    "worldbuilding": {"icon": "🎭", "color": "#6366f1", "href": "https://masks.kaleb.one", "app": "Masks Wiki"},
    "music":         {"icon": "🎵", "color": "#ec4899", "href": "https://music.kaleb.one", "app": "Music"},
    "wishlist":      {"icon": "🎁", "color": "#f43f5e", "href": "https://wish.kaleb.one", "app": "Wishlist"},
}

# ── Helpers ──────────────────────────────────────────────────────────────

def read_md(path):
    """Read markdown file, return (frontmatter_dict, body_str)."""
    with open(path) as f:
        content = f.read()
    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            try:
                fm = yaml.safe_load(parts[1])
            except yaml.YAMLError:
                fm = {}
            return fm or {}, parts[2].strip()
    return {}, content.strip()


def md_to_html(md_text):
    """Convert vault markdown to styled HTML."""
    md_text = re.sub(r'^---$', '<hr>', md_text, flags=re.MULTILINE)
    md_text = re.sub(r'^#### (.+)$', r'<h4>\1</h4>', md_text, flags=re.MULTILINE)
    md_text = re.sub(r'^### (.+)$', r'<h3>\1</h3>', md_text, flags=re.MULTILINE)
    md_text = re.sub(r'^## (.+)$', r'<h2>\1</h2>', md_text, flags=re.MULTILINE)
    md_text = re.sub(r'^# (.+)$', r'<h1>\1</h1>', md_text, flags=re.MULTILINE)

    # Tables
    lines = md_text.split('\n')
    result = []
    in_table = False
    table_rows = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith('|') and stripped.endswith('|'):
            if re.match(r'^\|[\s\-:|]+\|$', stripped):
                continue
            cells = [c.strip() for c in stripped.split('|')[1:-1]]
            table_rows.append(cells)
            in_table = True
        else:
            if in_table and table_rows:
                result.append(render_table(table_rows))
                table_rows = []
                in_table = False
            result.append(line)
    if table_rows:
        result.append(render_table(table_rows))
    md_text = '\n'.join(result)

    # Checkbox items
    md_text = re.sub(
        r'^- \[([ x])\] (.+)$',
        lambda m: '<li class="check-item"><input type="checkbox" ' + ('checked ' if m.group(1) == 'x' else '') + 'disabled><span>' + m.group(2) + '</span></li>',
        md_text, flags=re.MULTILINE
    )

    # Bold + italic
    md_text = re.sub(r'\*\*\*(.+?)\*\*\*', r'<strong><em>\1</em></strong>', md_text)
    md_text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', md_text)
    md_text = re.sub(r'\*(.+?)\*', r'<em>\1</em>', md_text)

    # Wikilinks
    md_text = re.sub(r'\[\[([^\]]+)\]\]', r'<a class="wikilink" href="/#\1">\1</a>', md_text)

    # Inline links
    md_text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2">\1</a>', md_text)

    # Unordered lists (non-checkbox)
    md_text = re.sub(r'^- (.+)$', r'<li>\1</li>', md_text, flags=re.MULTILINE)

    # Wrap consecutive <li> in <ul>
    md_text = re.sub(r'((?:<li[^>]*>.*?</li>\n?)+)', r'<ul>\1</ul>', md_text)

    # Paragraphs
    lines = md_text.split('\n')
    processed = []
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith('<') and not stripped.startswith('|'):
            processed.append('<p>' + line + '</p>')
        else:
            processed.append(line)
    md_text = '\n'.join(processed)

    # Blockquotes
    md_text = re.sub(r'^> (.+)$', r'<blockquote>\1</blockquote>', md_text, flags=re.MULTILINE)

    return md_text


def render_table(rows):
    if not rows:
        return ''
    h = '<table><thead><tr>'
    for cell in rows[0]:
        h += '<th>' + cell + '</th>'
    h += '</tr></thead><tbody>'
    for row in rows[1:]:
        h += '<tr>'
        for cell in row:
            h += '<td>' + cell + '</td>'
        h += '</tr>'
    h += '</tbody></table>'
    return h


def safe_slug(name):
    slug = name.lower().strip()
    slug = re.sub(r'[^\w\s-]', '', slug)
    slug = re.sub(r'[\s_]+', '-', slug)
    return slug.strip('-') or 'untitled'


def scan_files(path):
    """Walk directory, collect .md files with metadata."""
    files = []
    if not os.path.isdir(path):
        return files
    for root, dirs, fnames in os.walk(path):
        for fn in fnames:
            if not fn.endswith('.md'):
                continue
            fpath = os.path.join(root, fn)
            fm, body = read_md(fpath)
            title = fm.get('title', '') or fn.replace('.md', '').replace('-', ' ').replace('_', ' ').title()
            files.append({
                'filename': fn,
                'title': title,
                'domain': fm.get('domain', ''),
                'status': fm.get('status', ''),
                'tags': fm.get('tags', []),
                'body': body,
                'body_html': md_to_html(body),
                'slug': safe_slug(os.path.splitext(fn)[0]),
            })
    return files


def label_for(key):
    if key == 'notes':
        return 'Personal Notes'
    return key.replace('-', ' ').replace('_', ' ').title()


# ── Build ────────────────────────────────────────────────────────────────

def build():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Collect data
    domain_data = {}
    for dk, meta in PERSONAL_DOMAINS.items():
        dpath = os.path.join(VAULT_DIR, 'domains', dk)
        files = scan_files(dpath)
        domain_data[dk] = {**meta, 'files': files, 'key': dk}

    section_data = {}
    for sk, meta in VAULT_SECTIONS.items():
        spath = os.path.join(VAULT_DIR, sk)
        if sk == 'notes':
            spath = os.path.join(VAULT_DIR, 'notes', 'personal')
        files = scan_files(spath)
        section_data[sk] = {**meta, 'files': files, 'key': sk}

    # Build index
    build_index(domain_data, section_data)

    # Build domain pages
    for dk, data in domain_data.items():
        build_domain_page(dk, data)
    for sk, data in section_data.items():
        build_domain_page(sk, data)

    # Build note pages
    for dk, data in domain_data.items():
        for f in data['files']:
            build_note_page(f, data, dk)
    for sk, data in section_data.items():
        for f in data['files']:
            build_note_page(f, data, sk)

    # Write manifest for search
    manifest = []
    for dk, data in domain_data.items():
        for f in data['files']:
            manifest.append({'title': f['title'], 'domain': dk, 'slug': f['slug'], 'tags': f['tags']})
    for sk, data in section_data.items():
        for f in data['files']:
            manifest.append({'title': f['title'], 'domain': sk, 'slug': f['slug'], 'tags': f['tags']})

    with open(os.path.join(OUTPUT_DIR, 'manifest.json'), 'w') as fh:
        json.dump(manifest, fh, indent=2)

    total = sum(len(d['files']) for d in domain_data.values()) + sum(len(s['files']) for s in section_data.values())
    print("[brain] Built " + str(total) + " notes across " + str(len(domain_data) + len(section_data)) + " sections")
    print("[brain] Output: " + OUTPUT_DIR)


def build_index(domain_data, section_data):
    total_notes = sum(len(d['files']) for d in domain_data.values()) + sum(len(s['files']) for s in section_data.values())
    total_domains = len(domain_data)
    total_graduated = len(GRADUATED_DOMAINS)

    # All files for open loops + insights
    all_files = []
    for dk, data in domain_data.items():
        for f in data['files']:
            f['_dk'] = dk
            f['_icon'] = data['icon']
            all_files.append(f)
    for sk, data in section_data.items():
        for f in data['files']:
            f['_dk'] = sk
            f['_icon'] = data['icon']
            all_files.append(f)

    open_loops = [f for f in all_files if f.get('status') == 'loop' or 'loop' in f.get('tags', [])]

    # ── Build HTML sections ──

    # Domain cards
    domain_cards = ''
    for dk, data in domain_data.items():
        fc = len(data['files'])
        links = ''
        for f in data['files'][:5]:
            links += '<a href="/notes/' + dk + '/' + f['slug'] + '.html" class="note-link">' + f['title'] + '</a>'
        if fc > 5:
            links += '<a href="/domains/' + dk + '.html" class="note-link more-link">+' + str(fc - 5) + ' more →</a>'
        domain_cards += (
            '<div class="glass-card domain-card" data-domain="' + dk + '" style="--domain-color: ' + data['color'] + '">'
            '<div class="card-header"><span class="card-icon">' + data['icon'] + '</span>'
            '<h3>' + label_for(dk) + '</h3>'
            '<span class="badge">' + str(fc) + '</span></div>'
            '<p class="card-desc">' + data['desc'] + '</p>'
            '<div class="card-links">' + links + '</div>'
            '<a href="/domains/' + dk + '.html" class="card-launch">Open Domain →</a></div>\n'
        )

    # Section cards
    section_cards = ''
    for sk, data in section_data.items():
        fc = len(data['files'])
        links = ''
        for f in data['files'][:5]:
            links += '<a href="/notes/' + sk + '/' + f['slug'] + '.html" class="note-link">' + f['title'] + '</a>'
        if fc > 5:
            links += '<a href="/domains/' + sk + '.html" class="note-link more-link">+' + str(fc - 5) + ' more →</a>'
        section_cards += (
            '<div class="glass-card domain-card" data-domain="' + sk + '" style="--domain-color: ' + data['color'] + '">'
            '<div class="card-header"><span class="card-icon">' + data['icon'] + '</span>'
            '<h3>' + label_for(sk) + '</h3>'
            '<span class="badge">' + str(fc) + '</span></div>'
            '<p class="card-desc">' + data['desc'] + '</p>'
            '<div class="card-links">' + links + '</div>'
            '<a href="/domains/' + sk + '.html" class="card-launch">Open Section →</a></div>\n'
        )

    # Graduated cards
    graduated_cards = ''
    for gk, gdata in GRADUATED_DOMAINS.items():
        graduated_cards += (
            '<div class="glass-card app-card" data-domain="' + gk + '" style="--domain-color: ' + gdata['color'] + '">'
            '<div class="card-header"><span class="card-icon">' + gdata['icon'] + '</span>'
            '<h3>' + gdata['app'] + '</h3><span class="status-pip live"></span></div>'
            '<p class="card-desc">' + gk.replace('-', ' ').title() + '</p>'
            '<a href="' + gdata['href'] + '" class="card-launch" target="_blank">Launch ' + gdata['app'] + ' →</a></div>\n'
        )

    # Open loops
    loops_html = ''
    for f in open_loops[:8]:
        loops_html += '<div class="loop-item"><span class="loop-icon">' + f['_icon'] + '</span><a href="/notes/' + f['_dk'] + '/' + f['slug'] + '.html">' + f['title'] + '</a></div>\n'
    if not open_loops:
        loops_html = '<p class="empty-state">No open loops — all clear.</p>'

    # Insights
    insights = generate_insights(domain_data, section_data, all_files)
    insights_html = ''
    for ins in insights:
        insights_html += '<div class="insight-item"><span class="insight-icon">' + ins['icon'] + '</span><span class="insight-text">' + ins['text'] + '</span></div>\n'

    # Now read the template and inject
    with open(os.path.join(TEMPLATE_DIR, 'index.html')) as fh:
        template_html = fh.read()

    # Build the full page by replacing placeholders
    full_html = template_html
    full_html = full_html.replace('<!-- PLACEHOLDER: topbar -->',
        '<nav class="topbar">'
        '<div class="topbar-left"><span class="topbar-logo">🧠 brain</span><span class="topbar-subtitle">Mission Control + Notes</span></div>'
        '<div class="topbar-right">'
        '<a href="#notes" class="topbar-btn active">Notes</a>'
        '<a href="#ecosystem" class="topbar-btn">Apps</a>'
        '<a href="#insights" class="topbar-btn">Insights</a>'
        '</div></nav>')

    full_html = full_html.replace('<!-- PLACEHOLDER: search -->',
        '<div class="search-wrap">'
        '<span class="search-icon">⌕</span>'
        '<input type="text" class="search-input" id="searchInput" placeholder="Search notes… (Ctrl+K)" autocomplete="off">'
        '<div class="search-results" id="searchResults"></div></div>')

    full_html = full_html.replace('<!-- PLACEHOLDER: stats -->',
        '<div class="stats-row">'
        '<div class="stat-card"><div class="stat-value">' + str(total_notes) + '</div><div class="stat-label">Personal Notes</div></div>'
        '<div class="stat-card"><div class="stat-value">' + str(total_domains) + '</div><div class="stat-label">Active Domains</div></div>'
        '<div class="stat-card"><div class="stat-value">' + str(total_graduated) + '</div><div class="stat-label">Live Apps</div></div>'
        '<div class="stat-card"><div class="stat-value">' + str(len(open_loops)) + '</div><div class="stat-label">Open Loops</div></div>'
        '</div>')

    full_html = full_html.replace('<!-- PLACEHOLDER: insights -->',
        '<section id="insights" class="insights-panel">'
        '<h2 class="section-title">💡 Actionable Insights</h2>'
        + insights_html + '</section>')

    full_html = full_html.replace('<!-- PLACEHOLDER: loops -->',
        '<section class="loops-panel"><h2 class="section-title">🔄 Open Loops</h2>'
        '<div class="glass-card">' + loops_html + '</div></section>')

    full_html = full_html.replace('<!-- PLACEHOLDER: personal_domains -->',
        '<section id="notes"><h2 class="section-title">📝 Personal Notes</h2>'
        '<div class="domain-grid">' + domain_cards + section_cards + '</div></section>')

    full_html = full_html.replace('<!-- PLACEHOLDER: ecosystem -->',
        '<section id="ecosystem"><h2 class="section-title">🚀 App Ecosystem</h2>'
        '<div class="app-grid">' + graduated_cards + '</div></section>')

    full_html = full_html.replace('<!-- PLACEHOLDER: footer -->',
        '<div class="footer">brain.kaleb.one — Personal Notes + Mission Control<br>'
        '<span style="color:var(--text-muted);">Built from second-brain-vault</span></div>')

    full_html = full_html.replace('<!-- PLACEHOLDER: script -->',
        '<script>\n'
        'var manifest=[];fetch("/manifest.json").then(function(r){return r.json()}).then(function(data){manifest.push.apply(manifest,data)}).catch(function(){});\n'
        'var si=document.getElementById("searchInput"),sr=document.getElementById("searchResults");\n'
        'si.addEventListener("input",function(e){var q=e.target.value.toLowerCase().trim();if(!q||manifest.length===0){sr.classList.remove("visible");return;}'
        'var results=manifest.filter(function(item){return item.title.toLowerCase().indexOf(q)>=0||item.tags.some(function(t){return t.toLowerCase().indexOf(q)>=0})||item.domain.toLowerCase().indexOf(q)>=0}).slice(0,10);'
        'if(results.length===0){sr.innerHTML="<div class=\\"search-result\\"><span class=\\"result-title\\" style=\\"color:var(--text-muted)\\">No results</span></div>";sr.classList.add("visible");return;}'
        'sr.innerHTML=results.map(function(r){return"<a href=\\"/notes/"+r.domain+"/"+r.slug+".html\\" class=\\"search-result\\"><span class=\\"result-domain\\">"+r.domain+"</span><span class=\\"result-title\\">"+r.title+"</span></a>"}join("");sr.classList.add("visible");});\n'
        'si.addEventListener("blur",function(){setTimeout(function(){sr.classList.remove("visible")},200)});\n'
        'si.addEventListener("focus",function(){if(si.value.trim())si.dispatchEvent(new Event("input"))});\n'
        'document.addEventListener("keydown",function(e){if((e.ctrlKey||e.metaKey)&&e.key==="k"){e.preventDefault();si.focus();si.select();}if(e.key==="Escape"){sr.classList.remove("visible");si.blur();}});\n'
        'document.querySelectorAll(".topbar-btn").forEach(function(btn){btn.addEventListener("click",function(){document.querySelectorAll(".topbar-btn").forEach(function(b){b.classList.remove("active")});btn.classList.add("active");});});\n'
        '</script>')

    with open(os.path.join(OUTPUT_DIR, 'index.html'), 'w') as fh:
        fh.write(full_html)


def build_domain_page(domain_key, data):
    lbl = label_for(domain_key)
    files_html = ''
    for f in data['files']:
        tags_html = ' '.join('<span class="tag">' + t + '</span>' for t in f.get('tags', [])[:4])
        status_html = ''
        if f.get('status') and f['status'] != 'active':
            status_html = '<span class="status-tag ' + f['status'] + '">' + f['status'] + '</span>'
        excerpt = f['body'][:150].replace('\n', ' ')
        files_html += (
            '<div class="glass-card note-card">'
            '<div class="note-card-header"><h3><a href="/notes/' + domain_key + '/' + f['slug'] + '.html">' + f['title'] + '</a></h3>' + status_html + '</div>'
            '<div class="tag-row">' + tags_html + '</div>'
            '<p class="note-excerpt">' + excerpt + '…</p></div>\n'
        )
    if not data['files']:
        files_html = '<p class="empty-state">No notes in this section yet.</p>'

    with open(os.path.join(TEMPLATE_DIR, 'domain.html')) as fh:
        tmpl = fh.read()

    page = tmpl
    page = page.replace('{{TITLE}}', lbl)
    page = page.replace('{{LABEL}}', lbl)
    page = page.replace('{{ICON}}', data['icon'])
    page = page.replace('{{DESC}}', data['desc'])
    page = page.replace('{{DOMAIN_COLOR}}', data['color'])
    page = page.replace('{{FILES}}', files_html)

    domain_dir = os.path.join(OUTPUT_DIR, 'domains')
    os.makedirs(domain_dir, exist_ok=True)
    with open(os.path.join(domain_dir, domain_key + '.html'), 'w') as fh:
        fh.write(page)


def build_note_page(file_data, domain_data, domain_key):
    lbl = label_for(domain_key)

    meta_html = '<span class="meta-tag">' + domain_key + '</span>'
    if file_data.get('status'):
        meta_html += ' <span class="meta-status ' + file_data['status'] + '">' + file_data['status'] + '</span>'
    for t in file_data.get('tags', [])[:6]:
        meta_html += ' <span class="meta-tag">' + t + '</span>'

    with open(os.path.join(TEMPLATE_DIR, 'note.html')) as fh:
        tmpl = fh.read()

    page = tmpl
    page = page.replace('{{TITLE}}', file_data['title'])
    page = page.replace('{{LABEL}}', lbl)
    page = page.replace('{{ICON}}', domain_data['icon'])
    page = page.replace('{{DOMAIN_COLOR}}', domain_data['color'])
    page = page.replace('{{DOMAIN_KEY}}', domain_key)
    page = page.replace('{{META}}', meta_html)
    page = page.replace('{{BODY}}', file_data['body_html'])

    note_dir = os.path.join(OUTPUT_DIR, 'notes', domain_key)
    os.makedirs(note_dir, exist_ok=True)
    with open(os.path.join(note_dir, file_data['slug'] + '.html'), 'w') as fh:
        fh.write(page)


def generate_insights(domain_data, section_data, all_files):
    insights = []
    no_fm = sum(1 for f in all_files if not f.get('status') and not f.get('tags'))
    if no_fm > 5:
        insights.append({'icon': '🏷️', 'text': str(no_fm) + ' notes missing frontmatter — add status & tags for better search.'})
    inbox = section_data.get('inbox', {}).get('files', [])
    if len(inbox) > 2:
        insights.append({'icon': '📥', 'text': 'Inbox has ' + str(len(inbox)) + ' items — review and route them.'})
    if domain_data.get('health', {}).get('files'):
        insights.append({'icon': '💪', 'text': 'Health domain active — keep tracking gout triggers and weight milestones.'})
    if domain_data.get('novel', {}).get('files'):
        insights.append({'icon': '✍️', 'text': 'Novel project has active notes — review PROGRESS.md and set a writing session.'})
    if domain_data.get('tools', {}).get('files'):
        insights.append({'icon': '🔧', 'text': 'Tools domain is paused — review ROADMAP.md when ready to resume.'})
    insights.append({'icon': '🚀', 'text': 'Ecosystem has ' + str(len(GRADUATED_DOMAINS)) + ' live apps — check watch.kaleb.one and read.kaleb.one for recent activity.'})
    return insights[:6]


if __name__ == '__main__':
    build()