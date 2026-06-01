import React from 'react';

/**
 * Renderiza una fuente documental como "sello legal".
 *
 * El backend (T08 / OE4) emite cada fuente con el formato:
 *   "{documento} · {sección} · v{ver} {año} · [Categoría – Nombre]"
 *
 * Aquí la dividimos por el separador " · " y resaltamos cada parte
 * con su propio rol visual.
 */
function SourceBadge({ fuente, index }) {
  const partes = (fuente || '').split(' · ').map((p) => p.trim()).filter(Boolean);

  const documento = partes[0] || 'Documento sin nombre';
  const resto = partes.slice(1);

  // El último segmento suele venir entre corchetes con la categoría.
  const categoria = resto.find((p) => p.startsWith('['));
  const meta = resto.filter((p) => !p.startsWith('['));

  return (
    <li className="source-badge">
      <span className="source-badge__index">{String(index + 1).padStart(2, '0')}</span>
      <div className="source-badge__body">
        <span className="source-badge__doc">{documento}</span>
        {meta.length > 0 && (
          <span className="source-badge__meta">
            {meta.map((m, i) => (
              <span key={i} className="source-badge__meta-chip">{m}</span>
            ))}
          </span>
        )}
        {categoria && (
          <span className="source-badge__categoria">
            {categoria.replace(/^\[|\]$/g, '')}
          </span>
        )}
      </div>
    </li>
  );
}

export default SourceBadge;
