"""
SilverCare Concierge — MCP Server
Exposes 4 Langflow flows as MCP tools callable by IBM Bob.

Requirements:
    pip install "mcp<2.0.0" httpx python-dotenv

Run:
    python mcp_server.py
"""

import asyncio
import os
import json
from typing import Any
import httpx
from dotenv import load_dotenv

# MCP SDK (pinned <2.0.0 per hackathon requirement)
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp import types

load_dotenv()

# ── Config ────────────────────────────────────────────────────────────────────
LANGFLOW_BASE_URL = os.getenv("LANGFLOW_BASE_URL", "http://127.0.0.1:7860")
LANGFLOW_API_KEY  = os.getenv("LANGFLOW_API_KEY", "")

# Flow IDs — replace with actual IDs from your Langflow project
FLOW_IDS = {
    "check_medication_schedule":    os.getenv("FLOW_MEDICATION_SCHEDULE", ""),
    "check_drug_interaction":       os.getenv("FLOW_DRUG_INTERACTION", ""),
    "report_health_symptom":        os.getenv("FLOW_HEALTH_SYMPTOM", ""),
    "generate_caregiver_leave_request": os.getenv("FLOW_CAREGIVER_LEAVE", ""),
}

HEADERS = {
    "x-api-key": LANGFLOW_API_KEY,
    "Content-Type": "application/json",
}

# ── Langflow helper ───────────────────────────────────────────────────────────

async def run_langflow(flow_id: str, input_value: str, tweaks: dict = None) -> str:
    """Call a Langflow flow and return the text output."""
    url = f"{LANGFLOW_BASE_URL}/api/v1/run/{flow_id}"
    payload = {
        "input_value": input_value,
        "output_type": "chat",
        "input_type": "chat",
        "tweaks": tweaks or {},
    }
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(url, headers=HEADERS, json=payload)
        resp.raise_for_status()
        data = resp.json()
        # Extract text from Langflow response structure
        try:
            outputs = data["outputs"][0]["outputs"][0]
            return outputs["results"]["message"]["text"]
        except (KeyError, IndexError):
            return json.dumps(data)


# ── MCP Server ────────────────────────────────────────────────────────────────

server = Server("silvercare-concierge")


@server.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="check_medication_schedule",
            description=(
                "Cek jadwal minum obat lansia berdasarkan resep dokter yang tersimpan. "
                "Gunakan tool ini saat lansia bertanya kapan harus minum obat, obat apa yang "
                "harus diminum sekarang, atau ingin melihat jadwal harian mereka."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "elderly_name": {
                        "type": "string",
                        "description": "Nama lengkap lansia",
                    },
                    "current_time": {
                        "type": "string",
                        "description": "Waktu saat ini, contoh: '08:00' atau '08:00 pagi'",
                    },
                    "question": {
                        "type": "string",
                        "description": "Pertanyaan dari lansia tentang jadwal obatnya",
                    },
                },
                "required": ["elderly_name", "current_time", "question"],
            },
        ),
        types.Tool(
            name="check_drug_interaction",
            description=(
                "Periksa apakah dua atau lebih obat aman diminum bersamaan. "
                "Gunakan tool ini saat lansia atau caregiver ingin memastikan kombinasi "
                "obat tidak berbahaya sebelum dikonsumsi."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "drug_list": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Daftar nama obat yang ingin dicek interaksinya",
                    },
                },
                "required": ["drug_list"],
            },
        ),
        types.Tool(
            name="report_health_symptom",
            description=(
                "Analisis gejala kesehatan yang dilaporkan lansia dan nilai tingkat urgensinya. "
                "Gunakan tool ini saat lansia melaporkan gejala tidak nyaman, pusing, mual, "
                "atau efek samping yang mungkin terkait dengan obat yang diminum. "
                "PENTING: Tool ini BUKAN untuk diagnosis — hanya penilaian urgensi."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "symptom_description": {
                        "type": "string",
                        "description": "Deskripsi gejala yang dirasakan lansia",
                    },
                    "last_medication_taken": {
                        "type": "string",
                        "description": "Nama obat terakhir yang diminum beserta waktunya",
                    },
                },
                "required": ["symptom_description", "last_medication_taken"],
            },
        ),
        types.Tool(
            name="generate_caregiver_leave_request",
            description=(
                "Buat draft surat pengajuan Caregiver Leave ke HR untuk karyawan yang "
                "perlu merawat orang tua. Gunakan tool ini saat karyawan ingin mengajukan "
                "cuti untuk mendampingi orang tua ke dokter atau kondisi medis tertentu."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "employee_name": {
                        "type": "string",
                        "description": "Nama lengkap karyawan yang mengajukan",
                    },
                    "medical_reason": {
                        "type": "string",
                        "description": "Alasan medis pengajuan cuti (kondisi orang tua)",
                    },
                    "duration_days": {
                        "type": "integer",
                        "description": "Jumlah hari cuti yang diajukan",
                    },
                    "parent_name": {
                        "type": "string",
                        "description": "Nama orang tua / anggota keluarga yang dirawat",
                    },
                    "relationship": {
                        "type": "string",
                        "description": "Hubungan dengan orang yang dirawat, contoh: Ibu, Ayah",
                    },
                },
                "required": [
                    "employee_name", "medical_reason",
                    "duration_days", "parent_name", "relationship",
                ],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[types.TextContent]:
    flow_id = FLOW_IDS.get(name)
    if not flow_id:
        return [types.TextContent(
            type="text",
            text=f"Error: Flow ID untuk '{name}' belum dikonfigurasi. "
                 f"Set environment variable FLOW_{name.upper()}.",
        )]

    # Serialize arguments as the input message to Langflow
    input_value = json.dumps(arguments, ensure_ascii=False)

    try:
        result = await run_langflow(flow_id, input_value)
        return [types.TextContent(type="text", text=result)]
    except httpx.HTTPStatusError as e:
        return [types.TextContent(
            type="text",
            text=f"Langflow error ({e.response.status_code}): {e.response.text}",
        )]
    except Exception as e:
        return [types.TextContent(type="text", text=f"Error: {str(e)}")]


# ── Entry point ───────────────────────────────────────────────────────────────

async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


if __name__ == "__main__":
    asyncio.run(main())
