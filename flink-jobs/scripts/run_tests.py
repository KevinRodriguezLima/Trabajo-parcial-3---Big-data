import os
import sys
import unittest

# Asegurar que el directorio raíz de la aplicación y flink-jobs estén en sys.path
root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
flink_jobs_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, root_dir)
sys.path.insert(0, flink_jobs_dir)

def run_all_tests():
    print("=" * 70)
    print(" EJECUTANDO SUITE DE PRUEBAS UNITARIAS E INTEGRACIÓN (PARTE C - FLINK)")
    print("=" * 70)
    
    loader = unittest.TestLoader()
    suite = loader.discover(start_dir=os.path.join(flink_jobs_dir, "tests"), pattern="test_*.py")
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    print("=" * 70)
    if result.wasSuccessful():
        print(" RESULTADO: TODAS LAS PRUEBAS PASARON EXITOSAMENTE (OK)")
    else:
        print(f" RESULTADO: FALLARON {len(result.failures)} PRUEBAS Y {len(result.errors)} ERRORES")
    print("=" * 70)
    
    return 0 if result.wasSuccessful() else 1

if __name__ == "__main__":
    sys.exit(run_all_tests())
