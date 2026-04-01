#!/usr/bin/env python3
"""
compile_translations.py
Script pour compiler les fichiers .po en .mo
"""
import os
import subprocess
import sys

def compile_po_file(po_file, mo_file):
    """Compile un fichier .po en .mo en utilisant Python"""
    try:
        # Essayer avec msgfmt si disponible
        result = subprocess.run(
            ['msgfmt', po_file, '-o', mo_file],
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            print(f"✅ {po_file} → {mo_file}")
            return True
        else:
            raise Exception("msgfmt failed")
            
    except (FileNotFoundError, Exception):
        # Fallback: use the polib module if available
        try:
            import polib
            po = polib.pofile(po_file)
            po.save_as_mofile(mo_file)
            print(f"✅ {po_file} → {mo_file} (via polib)")
            return True
        except ImportError:
            print(f"❌ {po_file}: msgfmt et polib non disponibles")
            print("   Installez avec: pip install polib")
            return False

def main():
    """Compile all .po files into .mo"""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    locales_dir = os.path.join(script_dir, 'locales')
    
    if not os.path.exists(locales_dir):
        print(f"❌ Dossier locales/ introuvable: {locales_dir}")
        return False
    
    languages = ['es', 'fr']
    success_count = 0
    total_count = 0
    
    for lang in languages:
        total_count += 1
        po_file = os.path.join(locales_dir, lang, 'LC_MESSAGES', 'app.po')
        mo_file = os.path.join(locales_dir, lang, 'LC_MESSAGES', 'app.mo')
        
        if not os.path.exists(po_file):
            print(f"⚠️  {po_file} introuvable")
            continue
        
        # Create the folder if necessary
        os.makedirs(os.path.dirname(mo_file), exist_ok=True)
        
        if compile_po_file(po_file, mo_file):
            success_count += 1
    
    print(f"\n✅ Compilation terminée: {success_count}/{total_count} réussies")
    return success_count == total_count

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)