"""
Script de vérification du système de traduction
À exécuter pour diagnostiquer les problèmes
"""

import os
import sys

print("=" * 60)
print("🔍 VÉRIFICATION SYSTÈME DE TRADUCTION")
print("=" * 60)

# ========== 1. VÉRIFIER LES FICHIERS .PO ==========
print("\n1️⃣ FICHIERS .PO")
print("-" * 60)

po_files = {
    "es": "translations/es.po",
    "fr": "translations/fr.po"
}

for lang, filepath in po_files.items():
    if os.path.exists(filepath):
        print(f"✅ {lang}: {filepath} EXISTE")
        
        # Compter les traductions
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
            msgid_count = content.count('msgid "')
            msgstr_count = content.count('msgstr "')
            print(f"   📊 {msgid_count} msgid / {msgstr_count} msgstr")
            
            # Vérifier clés PIN
            pin_keys = [
                "Código de Seguridad",
                "Ingrese el código PIN",
                "✓ Código correcto",
                "✗ Código incorrecto"
            ]
            
            for key in pin_keys:
                if f'msgid "{key}"' in content:
                    print(f"   ✅ Clé trouvée: '{key}'")
                else:
                    print(f"   ❌ Clé MANQUANTE: '{key}'")
    else:
        print(f"❌ {lang}: {filepath} INTROUVABLE")

# ========== 2. VÉRIFIER TRANSLATION.PY ==========
print("\n2️⃣ MODULE translation.py")
print("-" * 60)

try:
    from translation import _, change_language, get_current_language, TRANSLATIONS
    print("✅ Import réussi")
    
    # Vérifier structure TRANSLATIONS
    print(f"📊 Langues disponibles: {list(TRANSLATIONS.keys())}")
    
    for lang in ["es", "fr"]:
        if lang in TRANSLATIONS:
            count = len(TRANSLATIONS[lang])
            print(f"   {lang}: {count} traductions chargées")
            
            # Tester une clé
            test_key = "Código de Seguridad"
            if test_key in TRANSLATIONS[lang]:
                print(f"   ✅ Test '{test_key}' → '{TRANSLATIONS[lang][test_key]}'")
            else:
                print(f"   ❌ Clé '{test_key}' manquante en {lang}")
    
    # Test de traduction
    print("\n🧪 TEST DE TRADUCTION")
    for lang in ["es", "fr"]:
        change_language(lang)
        current = get_current_language()
        result = _("Código de Seguridad")
        print(f"   {lang}: _('Código de Seguridad') = '{result}' (langue={current})")
        
        if lang == "es" and result != "Código de Seguridad":
            print(f"   ⚠️ PROBLÈME: Attendu 'Código de Seguridad', obtenu '{result}'")
        elif lang == "fr" and result != "Code de Sécurité":
            print(f"   ⚠️ PROBLÈME: Attendu 'Code de Sécurité', obtenu '{result}'")
    
except ImportError as e:
    print(f"❌ Erreur import: {e}")
except Exception as e:
    print(f"❌ Erreur: {e}")
    import traceback
    traceback.print_exc()

# ========== 3. VÉRIFIER SETTINGS.JSON ==========
print("\n3️⃣ CONFIGURATION settings.json")
print("-" * 60)

settings_path = "settings/settings.json"
if os.path.exists(settings_path):
    print(f"✅ {settings_path} EXISTE")
    
    import json
    with open(settings_path, 'r') as f:
        config = json.load(f)
        lang = config.get("language", "NON DÉFINI")
        print(f"   📌 Langue configurée: {lang}")
else:
    print(f"❌ {settings_path} INTROUVABLE")

# ========== 4. VÉRIFIER PINCODE DANS APP ==========
print("\n4️⃣ INTÉGRATION dans reload_all_screens()")
print("-" * 60)

try:
    # Lire main.py ou votre fichier app principal
    app_files = ["main.py", "app.py", "cobien.py"]
    
    for app_file in app_files:
        if os.path.exists(app_file):
            with open(app_file, 'r', encoding='utf-8') as f:
                content = f.read()
                
                if 'reload_all_screens' in content:
                    print(f"✅ reload_all_screens trouvé dans {app_file}")
                    
                    # Vérifier si pinCodeScreen est dans la liste
                    if "'pinCodeScreen'" in content or '"pinCodeScreen"' in content:
                        print("   ✅ 'pinCodeScreen' dans screens_to_update")
                    else:
                        print("   ❌ 'pinCodeScreen' ABSENT de screens_to_update")
                        print("   💡 Ajoutez 'pinCodeScreen' à la liste screens_to_update")
            break
    else:
        print("⚠️ Fichier principal non trouvé")
        
except Exception as e:
    print(f"❌ Erreur: {e}")

# ========== 5. INSTRUCTIONS ==========
print("\n" + "=" * 60)
print("📝 ACTIONS À FAIRE")
print("=" * 60)

print("""
Si des éléments sont marqués ❌, faites ces corrections :

1. Fichiers .po manquants ou incomplets :
   → Vérifiez translations/es.po et translations/fr.po
   → Assurez-vous que TOUTES les clés PIN sont présentes

2. translation.py ne fonctionne pas :
   → Vérifiez la structure du dictionnaire TRANSLATIONS
   → Testez manuellement : python -c "from translation import _; print(_('Código de Seguridad'))"

3. pinCodeScreen absent de reload_all_screens :
   → Éditez votre fichier app principal
   → Ajoutez 'pinCodeScreen' dans screens_to_update
   
   Exemple :
   screens_to_update = [
       'weather', 'events', 'day_events', 'board', 'contacts',
       'settings', 'button_colors', 'settings_notifications',
       'settings_rfid', 'weather_choice', 'joke_category', 'jokes',
       'pinCodeScreen'  # ✅ AJOUTER CETTE LIGNE
   ]

4. Tester après corrections :
   → Lancez l'app
   → Allez dans Settings → Language
   → Changez de langue
   → Revenez à l'écran PIN
   → Les textes doivent être traduits
""")

print("=" * 60)
print("✅ Vérification terminée")
print("=" * 60)