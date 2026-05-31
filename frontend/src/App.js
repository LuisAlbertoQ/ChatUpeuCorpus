import React, { useState } from 'react';
import './App.css';

const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

function App() {
  const [pregunta, setPregunta] = useState('');
  const [conversacion, setConversacion] = useState([]);
  const [cargando, setCargando] = useState(false);

  const enviarPregunta = async () => {
    if (!pregunta.trim()) return;
    setCargando(true);
    const nuevaConversacion = [...conversacion, { tipo: 'usuario', texto: pregunta }];
    setConversacion(nuevaConversacion);
    setPregunta('');

    try {
      const response = await fetch(`${API_URL}/consulta`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ pregunta: pregunta })
      });
      const data = await response.json();
      setConversacion([...nuevaConversacion, { tipo: 'chatbot', ...data }]);
    } catch (error) {
      setConversacion([...nuevaConversacion, { tipo: 'chatbot', respuesta: 'Error al conectar con el servidor.', fuentes: [] }]);
    }
    setCargando(false);
  };

  return (
    <div className="app-container">
      <header className="app-header">
        <h1>Chatbot UPeU</h1>
        <p className="disclaimer">Respuesta generada por inteligencia artificial. La UPeU no se hace responsable por el uso indebido de la información. Verifica con fuentes oficiales cuando sea necesario.</p>
      </header>
      <div className="chat-window">
        {conversacion.length === 0 && (
          <p className="welcome-message">Hola, soy un asistente basado en IA generativa. Mis respuestas se fundamentan en documentos institucionales oficiales de la Universidad Peruana Unión (reglamentos, instructivos, cronogramas y lineamientos vigentes). Recuerda que mi función es informativa y no reemplaza la validación administrativa oficial. Si necesitas resolver un trámite personal, contacta directamente con la oficina correspondiente.</p>
        )}
        {conversacion.map((msg, idx) => (
          <div key={idx} className={`message ${msg.tipo}`}>
            <p className="message-text">{msg.texto || msg.respuesta}</p>
            {msg.fuentes && msg.fuentes.length > 0 && (
              <div className="sources">
                <strong>Fuentes:</strong>
                <ul>
                  {msg.fuentes.map((fuente, i) => <li key={i}>{fuente}</li>)}
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
          placeholder="Escribe tu consulta sobre reglamentos UPeU..."
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