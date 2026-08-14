import React from 'react';
import ReactMarkdown from 'react-markdown';
import SourceBadge from './SourceBadge';

/**
 * Etiqueta visual asociada a cada tipo de mensaje del OE4 (sección 4).
 */
const META_TIPO = {
  M02: { rotulo: 'Respuesta verificada', tono: 'ok' },
  M03: { rotulo: 'Fuera de alcance', tono: 'aviso' },
  M04: { rotulo: 'Sin información suficiente', tono: 'alerta' },
  M05: { rotulo: 'Reformula tu pregunta', tono: 'info' },
  M06: { rotulo: 'Error técnico', tono: 'error' },
  M08: { rotulo: 'Límite de sesión alcanzado', tono: 'aviso' },
};

function Message({ mensaje }) {
  const esUsuario = mensaje.tipo === 'usuario';
  const tipoMsg = mensaje.tipo_mensaje;
  const meta = META_TIPO[tipoMsg];

  return (
    <article
      className={`msg msg--${esUsuario ? 'user' : 'bot'} ${
        meta ? `msg--${meta.tono}` : ''
      }`}
    >
      <header className="msg__head">
        <span className="msg__author">
          {esUsuario ? 'Tú' : 'Asistente UPeU'}
        </span>
        {meta && !esUsuario && (
          <span className={`msg__tag msg__tag--${meta.tono}`}>
            <span className="msg__tag-dot" />
            {meta.rotulo}
            <span className="msg__tag-code">{tipoMsg}</span>
          </span>
        )}
      </header>

      <div className="msg__body">
        <ReactMarkdown>
          {mensaje.texto || mensaje.respuesta || ''}
        </ReactMarkdown>
      </div>

      {!esUsuario && Array.isArray(mensaje.fuentes) && mensaje.fuentes.length > 0 && (
        <footer className="msg__sources">
          <p className="msg__sources-title">Fuentes verificables</p>
          <ul className="msg__sources-list">
            {mensaje.fuentes.map((f, i) => (
              <SourceBadge
                key={i}
                index={i}
                fuente={f}
                similitud={
                  Array.isArray(mensaje.debug_distancias)
                    ? (1 - mensaje.debug_distancias[i]) * 100
                    : null
                }
              />
            ))}
          </ul>
        </footer>
      )}

      {!esUsuario && typeof mensaje.tiempo_respuesta === 'number' && (
        <p className="msg__telemetry">
          <span>tiempo</span>
          <span className="msg__telemetry-value">
            {mensaje.tiempo_respuesta.toFixed(2)} s
          </span>
        </p>
      )}
    </article>
  );
}

export default Message;
