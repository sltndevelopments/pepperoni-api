#!/usr/bin/env python3
"""Add Google Tag Manager to all HTML files in public/."""
import os

GTM_HEAD = '''<!-- Google Tag Manager -->
<script>(function(w,d,s,l,i){w[l]=w[l]||[];w[l].push({'gtm.start':
new Date().getTime(),event:'gtm.js'});var f=d.getElementsByTagName(s)[0],
j=d.createElement(s),dl=l!='dataLayer'?'&l='+l:'';j.async=true;j.src=
'https://www.googletagmanager.com/gtm.js?id='+i+dl;f.parentNode.insertBefore(j,f);
})(window,document,'script','dataLayer','GTM-W2Q5S8HF');</script>
<!-- End Google Tag Manager -->
'''

GTM_BODY = '''<!-- Google Tag Manager (noscript) -->
<noscript><iframe src="https://www.googletagmanager.com/ns.html?id=GTM-W2Q5S8HF"
height="0" width="0" style="display:none;visibility:hidden"></iframe></noscript>
<!-- End Google Tag Manager (noscript) -->
'''

def add_gtm(content):
    if 'GTM-W2Q5S8HF' in content:
        return None  # already has GTM
    # Add script right after <head>
    if '<head>' in content and GTM_HEAD not in content:
        content = content.replace('<head>', '<head>\n' + GTM_HEAD, 1)
    # Add noscript right after <body> (handle <body> or <body ...>)
    import re
    body_match = re.search(r'<body[^>]*>', content)
    if body_match and GTM_BODY not in content:
        end = body_match.end()
        content = content[:end] + '\n' + GTM_BODY + content[end:]
    return content

def main():
    public = os.path.join(os.path.dirname(__file__), '..', 'public')
    count = 0
    for root, _, files in os.walk(public):
        for f in files:
            if f.endswith('.html'):
                path = os.path.join(root, f)
                with open(path, 'r', encoding='utf-8') as fp:
                    content = fp.read()
                new_content = add_gtm(content)
                if new_content is not None:
                    with open(path, 'w', encoding='utf-8') as fp:
                        fp.write(new_content)
                    count += 1
                    print(path)
    print(f'\nAdded GTM to {count} files')

if __name__ == '__main__':
    main()
