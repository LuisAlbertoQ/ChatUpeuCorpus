import React, { useEffect, useRef } from 'react';
import Message from './Message';

/**
 * Contenedor del hilo de conversación. Maneja:
 *   - scroll automático al último mensaje
 *   - empty state con el aviso M01 obtenido del backend
 *   - indicador de "pensando" mientras se espera respuesta
 */
function ChatWindow({ conversacion, mensajeBienvenida, cargando }) {
  const finRef = useRef(null);

  useEffect(() => {
    finRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' });
  }, [conversacion, cargando]);

  const vacio = conversacion.length === 0;

  return (
    <section className="chat" aria-live="polite">
      {vacio && (
        <div className="chat__empty">
          <p className="chat__empty-eyebrow">M01 · Aviso inicial</p>
          <p className="chat__empty-text">
            {mensajeBienvenida ||
              'Cargando el aviso de bienvenida…'}
          </p>
          <ul className="chat__hints">
            <li>“¿Cuáles son los plazos para la matrícula extemporánea?”</li>
            <li>“¿Qué requisitos pide la beca de rendimiento académico?”</li>
            <li>“¿Cómo solicito una constancia de estudios?”</li>
          </ul>
        </div>
      )}

      <div className="chat__stream">
        {conversacion.map((m, i) => (
          <Message key={i} mensaje={m} />
        ))}

        {cargando && (
          <div className="chat__thinking" role="status">
            <span className="chat__thinking-dot" />
            <span className="chat__thinking-dot" />
            <span className="chat__thinking-dot" />
            <span className="chat__thinking-label">Consultando el corpus…</span>
          </div>
        )}

        <div ref={finRef} />
      </div>
    </section>
  );
}

export default ChatWindow;
