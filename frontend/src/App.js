import React, { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import './App.css';

const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

function App() {
  const [pregunta, setPregunta] = useState('');
  const [conversacion, setConversacion] = useState([]);
  const [cargando, setCargando] = useState(false);

  const enviarPregunta = async () => {
    if (!pregunta.trim()) return;

    setCargando(true);

    const nuevaConversacion = [
      ...conversacion,
      { tipo: 'usuario', texto: pregunta }
    ];

    setConversacion(nuevaConversacion);
    setPregunta('');

    try {
      const response = await fetch(`${API_URL}/consulta`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ pregunta })
      });

      const data = await response.json();

      setConversacion([
        ...nuevaConversacion,
        { tipo: 'chatbot', ...data }
      ]);

    } catch (error) {
      setConversacion([
        ...nuevaConversacion,
        {
          tipo: 'chatbot',
          respuesta: 'Error al conectar con el servidor.',
          fuentes: []
        }
      ]);
    }

    setCargando(false);
  };

  return (
    <div className="app-container">
      <header className="app-header">
        <h1>Chatbot UPeU</h1>
        <p className="disclaimer">
          Respuesta generada por inteligencia artificial. Verifica con fuentes oficiales.
        </p>
      </header>

      <div className="chat-window">
        {conversacion.length === 0 && (
          <p className="welcome-message">
            Hola, soy un asistente basado en IA generativa...
          </p>
        )}

        {conversacion.map((msg, idx) => (
          <div key={idx} className={`message ${msg.tipo}`}>

            {/* MENSAJE DEL USUARIO O BOT */}
            <div className="message-text">
              <ReactMarkdown>
                {msg.texto || msg.respuesta}
              </ReactMarkdown>
            </div>

            {/* FUENTES */}
            {msg.fuentes && msg.fuentes.length > 0 && (
              <div className="sources">
                <strong>Fuentes:</strong>
                <ul>
                  {msg.fuentes.map((fuente, i) => (
                    <li key={i}>{fuente}</li>
                  ))}
                </ul>
              </div>
            )}

          </div>
        ))}
      </div>

      <div className="input-area">
        <input
          type="text"
          value={pregunta}
          onChange={(e) => setPregunta(e.target.value)}
          onKeyPress={(e) => e.key === 'Enter' && enviarPregunta()}
          placeholder="Escribe tu consulta..."
          disabled={cargando}
        />

        <button onClick={enviarPregunta} disabled={cargando}>
          {cargando ? '...' : 'Enviar'}
        </button>
      </div>
    </div>
  );
}

export default App;