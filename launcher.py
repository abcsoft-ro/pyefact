import sys
import multiprocessing
from streamlit.web import cli as stcli

# --- NOU: Verificare versiune Python ---
py_major, py_minor = sys.version_info[:2]
if py_major == 3 and py_minor >= 13:
    print("="*80)
    print("AVERTISMENT: Folosiți o versiune de Python (3.13+) care poate avea probleme de compatibilitate.")
    print("Anumite dependențe critice (ex: 'cryptography') pot să nu aibă încă versiuni stabile,")
    print("ceea ce poate duce la erori neașteptate, în special la autentificarea cu token USB.")
    print("\nRECOMANDARE:")
    print("  - Utilizați Python 3.11 pentru stabilitate maximă cu acest proiect.")
    print("  - Pentru a gestiona mai multe versiuni de Python pe același sistem, folosiți un manager de versiuni precum 'pyenv-win'.")
    print("="*80)

# Importăm funcția care trebuie să ruleze în procesul de fundal
from background_service import run_async_service

def start_background_service():
    """
    Funcția care inițiază și pornește procesul de fundal.
    """
    print("--- [Launcher] Se pornește serviciul de verificare a statusului facturilor ---")
    service_process = multiprocessing.Process(target=run_async_service, daemon=True)
    service_process.start()
    print(f"--- [Launcher] Serviciul a pornit cu succes. PID: {service_process.pid} ---")
    # Nu este necesar să returnăm procesul, deoarece este 'daemon' și va rula independent.

if __name__ == '__main__':
    # Această linie este esențială pentru a preveni erorile `multiprocessing` pe Windows.
    multiprocessing.freeze_support()

    # Pornim serviciul nostru de fundal o singură dată, la început.
    start_background_service()

    # Acum, lansăm aplicația Streamlit.
    # Acest cod este echivalentul rulării comenzii: `streamlit run efact.py`
    sys.argv = ["streamlit", "run", "efact.py", "--server.showEmailPrompt=false"]
    sys.exit(stcli.main())