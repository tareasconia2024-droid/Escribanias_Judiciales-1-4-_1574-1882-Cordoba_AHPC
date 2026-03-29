# AHPC – Escribanías Judiciales 1, 2, 3 y 4 (1574–1882)

Aplicación web Flask para consultar el índice de expedientes de las  
**Escribanías Judiciales del Archivo Histórico de la Provincia de Córdoba**

---

## Estructura

```
app2/
├── app.py                  ← Servidor Flask
├── ahpc_escribanias.db     ← Base de datos SQLite (18.906 registros)
├── requirements.txt
└── templates/
    ├── base.html
    ├── index.html
    ├── buscar.html
    ├── detalle.html
    └── estadisticas.html
```

## Instalación

```bash
pip install -r requirements.txt
python app.py
# → http://localhost:5002
```

## Funcionalidades

| Ruta | Descripción |
|------|-------------|
| `/` | Inicio con resumen del fondo |
| `/buscar` | Búsqueda por partes, causa, escribanía, año, legajo o texto libre |
| `/detalle/<id>` | Ficha completa del expediente |
| `/estadisticas` | Distribución por siglo, década, escribanía y causas frecuentes |
| `/api/buscar` | API JSON con paginación de 50 resultados |
| `/api/exportar-pdf` | PDF con los resultados de la búsqueda actual |

## Datos

- **18.906 expedientes** · Escribanías 1, 2, 3 y 4
- **Rango:** 1574–1882 (más de 3 siglos)
- Búsqueda de texto completo (FTS5) sobre partes y causas
- Fuente: `3_AHPC_PJ_Escribania_1_2_3_4_Juzgados_1574a1882_Indice_2025.xls`
