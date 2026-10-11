# SilverCare Concierge — Technical Documentation
## Hacktiv8 x IBM National Hackathon 2026

---

## Penggunaan IBM Langflow

**Workflow Overview:**
SilverCare menggunakan Langflow sebagai AI logic layer yang mengekspos 4 workflow sebagai MCP tools. Setiap workflow di-trigger oleh IBM Bob melalui protokol MCP dan mengembalikan hasil ke pengguna.

**Components yang Digunakan:**
| Component | Fungsi |
|---|---|
| Chat Input/Output | Entry dan exit point setiap flow |
| Astra DB (Vector Store) | Menyimpan dan meng-query data resep, interaksi obat, efek samping |
| Gemini Embeddings (text-embedding-004) | Mengubah teks menjadi vektor untuk semantic search |
| Gemini LLM (gemini-1.5-flash/pro) | Reasoning dan generasi jawaban |
| Prompt Template | Template dengan safety guardrails anti-halusinasi |
| Structured Output Parser | Memastikan output berbentuk JSON terstruktur |
| Conditional Router | Routing logika urgensi pada tool `report_health_symptom` |

**Input/Output per Tool:**

| Tool | Input | Output |
|---|---|---|
| `check_medication_schedule` | elderly_name, current_time, question | Jadwal obat dalam bahasa sederhana |
| `check_drug_interaction` | drug_list (array) | Status AMAN/PERINGATAN/BERBAHAYA + penjelasan |
| `report_health_symptom` | symptom_description, last_medication | urgency_level (1-5) + action_required |
| `generate_caregiver_leave_request` | employee_name, medical_reason, duration, parent | Draft surat formal HR |

**AI Agent Process:**
1. Bob menerima pesan dari user
2. Bob menentukan tool mana yang relevan berdasarkan konteks percakapan
3. Bob memanggil tool via MCP → Langflow flow berjalan
4. Langflow melakukan RAG query ke Astra DB untuk grounding data
5. Gemini LLM menghasilkan jawaban berdasarkan context yang ditemukan
6. Hasil dikembalikan ke Bob → disajikan ke user

---

## Penggunaan IBM Bob

**Fungsi Bob dalam SilverCare:**
IBM Bob berperan sebagai **Conversational Interface dan MCP Client** yang menjadi wajah aplikasi kepada dua segmen pengguna:

1. **Untuk Lansia:** Bob menjadi teman bicara yang memahami pertanyaan natural ("Obat saya yang pagi hari itu apa ya?") dan secara otomatis memanggil tool yang tepat.

2. **Untuk Karyawan (Sandwich Generation):** Bob membantu monitoring orang tua dan meng-generate dokumen HR tanpa perlu buka aplikasi lain.

**Process & Task Bob:**
- **Natural Language Understanding:** Memahami intent user (cek jadwal vs lapor gejala vs buat surat)
- **Tool Orchestration:** Memilih dan memanggil 1 atau lebih MCP tools secara berurutan jika perlu
- **Context Management:** Menjaga konteks percakapan antar giliran (siapa lansia-nya, obat apa yang sudah dibahas)
- **Safety Filter:** Bob tidak meneruskan permintaan yang meminta diagnosis atau perubahan dosis
- **Response Formatting:** Menyajikan jawaban Langflow dalam format yang mudah dibaca

**Interaksi dengan Sistem:**
Bob menggunakan config `.bob/mcp.json` untuk mendaftarkan Langflow sebagai MCP server. Saat user mengirim pesan, Bob memutuskan apakah perlu memanggil tool atau menjawab langsung dari konteks percakapan.

---

## Bagaimana Langflow & Bob Terintegrasi

**Data Flow Diagram:**
```
User (Lansia/Karyawan)
    │
    │ [Natural language message]
    ▼
IBM Bob (MCP Client)
    │ Tool selection via LLM reasoning
    │ [Structured tool call: name + arguments]
    ▼
MCP Protocol (stdio / streamablehttp)
    │
    ▼
mcp-proxy → Langflow REST API
    │ POST /api/v1/run/{flow_id}
    │ Headers: x-api-key
    │ Body: { input_value, tweaks }
    ▼
Langflow Flow Engine
    │ 1. Safety Gate (pre-filter)
    │ 2. Astra DB RAG Query
    │ 3. Prompt Assembly
    │ 4. Gemini LLM Inference
    │ 5. Output Parsing
    ▼
JSON Response → mcp-proxy → IBM Bob
    │ [Tool result as text]
    ▼
IBM Bob formats & presents to User
```

**Integrasi Teknis:**
- Bob membaca `.bob/mcp.json` → spawn `uvx mcp-proxy` sebagai child process
- `mcp-proxy` menerjemahkan MCP protocol (stdio) ↔ Langflow HTTP API
- Setiap Langflow flow di-expose sebagai satu MCP tool dengan schema JSON yang terdefinisi
- Bob mengirim argumen terstruktur; Langflow mengembalikan teks natural language

**Alternatif (Custom MCP Server):**
File `mcp_server.py` adalah Python MCP server kustom yang memanggil Langflow langsung via `httpx`, tanpa `mcp-proxy`. Digunakan saat butuh preprocessing argumen sebelum dikirim ke Langflow.

---

## Responsible AI

**Guardrails yang Diimplementasikan:**

| Guardrail | Implementasi |
|---|---|
| **Anti-hallucination** | LLM temperature 0.0–0.1; semua jawaban medis hanya dari RAG context |
| **Safety Gate** | Pre-filter prompt menolak permintaan diagnosis / perubahan dosis sebelum sampai ke LLM |
| **Fallback Response** | Jika data tidak ditemukan di RAG → hardcoded response "hubungi keluarga/dokter" |
| **Emergency Routing** | `report_health_symptom` dengan urgency ≥ 4 selalu menyertakan instruksi hubungi 119 |
| **No Speculative Advice** | System prompt eksplisit melarang saran dosis, penggantian obat, atau diagnosis |

**Privacy:**
- Data resep lansia disimpan di Astra DB dengan isolasi per-user (collection per family unit)
- Tidak ada data medis yang dikirim ke layanan eksternal selain Gemini API (untuk inference)
- Demo menggunakan synthetic data, bukan data pasien nyata
- API keys tidak pernah di-commit ke repository (stored di `.env`, di-ignore oleh git)

**Human-in-the-Loop:**
- Semua surat HR yang di-generate adalah **draft** — memerlukan review dan approval karyawan sebelum dikirim
- Caregiver (anak/keluarga) menerima notifikasi saat ada laporan gejala urgensi ≥ 3
- Tidak ada aksi otomatis (kirim pesan, submit ke HR) tanpa konfirmasi eksplisit dari user
- Untuk kondisi darurat, AI mengarahkan ke tenaga medis profesional, tidak menangani sendiri

**Disclaimer yang Ditampilkan ke User:**
> "SilverCare adalah alat bantu koordinasi perawatan, bukan pengganti dokter atau apoteker.
> Selalu konsultasikan perubahan pengobatan dengan tenaga medis profesional."
