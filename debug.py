import sys
sys.path.insert(0, '/app')
import config
import rag_pipeline
rag_pipeline.inicializar()

# Reproduce exactamente lo que hace generar_respuesta
resultado = rag_pipeline.generar_respuesta(
    pregunta='Cuales son los derechos del estudiante unionista',
    sesion_id='test-directo',
)
print('tipo_mensaje:', resultado['tipo_mensaje'])
print('distances:', resultado.get('debug_distancias'))
print('n_fuentes:', len(resultado.get('fuentes', [])))
print('respuesta:', resultado['respuesta'][:300])
print('error:', resultado.get('error', ''))
