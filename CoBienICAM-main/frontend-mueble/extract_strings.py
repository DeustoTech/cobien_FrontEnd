#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script d'extraction automatique des strings à traduire
Parcourt tous les fichiers Python et extrait les appels à _()

Usage: python3 extract_strings.py
"""

import os
import re
from collections import OrderedDict

def extract_from_file(filepath):
    """Extrait les strings traduisibles d'un fichier Python"""
    strings = []
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Pattern pour trouver _("texte") ou _('texte')
        pattern = r'_\(["\'](.+?)["\']\)'
        matches = re.findall(pattern, content)
        
        strings.extend(matches)
    
    except Exception as e:
        print(f"⚠️ Erreur lecture {filepath}: {e}")
    
    return strings

def scan_directory(directory='.'):
    """Scanne récursivement un dossier pour extraire toutes les strings"""
    all_strings = OrderedDict()
    
    for root, dirs, files in os.walk(directory):
        # Ignorer certains dossiers
        dirs[:] = [d for d in dirs if d not in ['.git', '__pycache__', 'venv', 'locales']]
        
        for file in files:
            if file.endswith('.py'):
                filepath = os.path.join(root, file)
                strings = extract_from_file(filepath)
                
                for string in strings:
                    if string not in all_strings:
                        all_strings[string] = filepath
    
    return all_strings

def generate_po_template(strings, output_file='locales/template.po'):
    """Génère un fichier .po template"""
    
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    
    with open(output_file, 'w', encoding='utf-8') as f:
        # Header
        f.write('msgid ""\n')
        f.write('msgstr ""\n')
        f.write('"Content-Type: text/plain; charset=UTF-8\\n"\n')
        f.write('"Language: LANG\\n"\n')
        f.write('\n')
        
        # Strings
        for string, filepath in strings.items():
            f.write(f'# {filepath}\n')
            f.write(f'msgid "{string}"\n')
            f.write(f'msgstr ""\n')
            f.write('\n')
    
    print(f"✅ Template généré: {output_file}")

def main():
    print("""
╔════════════════════════════════════════════════════════════╗
║         EXTRACTION DES STRINGS À TRADUIRE                  ║
╚════════════════════════════════════════════════════════════╝
""")
    
    # Scanner le projet
    print("🔍 Scan du projet...")
    strings = scan_directory('.')
    
    print(f"\n📊 Résultats:")
    print(f"   {len(strings)} strings uniques trouvées\n")
    
    # Afficher les strings
    print("📝 Strings extraites:\n")
    for i, (string, filepath) in enumerate(strings.items(), 1):
        print(f"   {i:3d}. \"{string}\"")
        print(f"        └─ {filepath}")
    
    # Générer template
    print(f"\n{'='*60}")
    generate_po_template(strings)
    print(f"{'='*60}\n")
    
    print("💡 Prochaines étapes:")
    print("   1. Copier locales/template.po vers locales/es/LC_MESSAGES/app.po")
    print("   2. Copier locales/template.po vers locales/fr/LC_MESSAGES/app.po")
    print("   3. Remplir les msgstr dans chaque fichier")
    print("   4. Compiler avec: python3 compile_translations.py")

if __name__ == "__main__":
    main()