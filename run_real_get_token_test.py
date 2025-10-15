import os
import sys
import traceback

# Adăugăm calea proiectului pentru a putea importa clasa Anafgettoken2
# Presupunem că acest script este rulat din directorul c:\pyefact
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__))))
from anaf_oauth2 import Anafgettoken2

def main():
    """
    Rulează un test de integrare pentru clasa Anafgettoken2 folosind utilitarul real 'get_token.class'.
    """
    print("===================================================================")
    print("   Test de integrare: Anafgettoken2 cu utilitarul 'get_token.class'")
    print("===================================================================\n")

    try:
        # Asigură-te că 'get_token.class' se află în directorul 'c:\pyefact'
        # sau ajustează 'java_class_path' dacă este în altă parte.
        java_class_path = "." # Directorul curent
        # Directorul unde se află fișierele .jar necesare (ex: json-20231013.jar)
        java_libs_dir = "." 
        java_class_name = "get_token" # Numele clasei reale

        classpath = os.pathsep.join([java_class_path, f"{java_libs_dir}{os.sep}*"])
        print(f"Se inițializează clientul pentru a rula: java -cp \"{classpath}\" {java_class_name}\n")
        
        client = Anafgettoken2(
            java_class_path=java_class_path,
            java_libs_path=java_libs_dir,
            java_class_name=java_class_name
        )

        print("Se apelează metoda get_new_token()...")
        token_info = client.get_new_token()

        print("\n✅ SUCCES! Token-urile au fost obținute:")
        print(f"   Access Token: {token_info.get('access_token')[:10]}...")
        print(f"   Refresh Token: {token_info.get('refresh_token')[:10]}...")
        print("\nℹ️ Verificați fișierele '.env' și 'token.json' pentru a confirma actualizarea.")

    except Exception as e:
        print("\n❌ EROARE! A apărut o problemă în timpul execuției:")
        # Afișăm eroarea completă pentru a facilita depanarea
        traceback.print_exc()

if __name__ == "__main__":
    main()
