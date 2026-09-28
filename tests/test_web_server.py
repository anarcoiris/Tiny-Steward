"""Unit tests for core/web_server.py FastAPI endpoints."""

from pathlib import Path
import time
from fastapi.testclient import TestClient
from core.web_server import app

client = TestClient(app)

def test_root_endpoint():
    response = client.get("/")
    assert response.status_code == 200

def test_status_endpoint():
    response = client.get("/api/status")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "online"
    assert "lock" in data

def test_telemetry_endpoint():
    response = client.get("/api/telemetry")
    assert response.status_code == 200
    data = response.json()
    assert "gpus" in data

def test_sessions_endpoint():
    response = client.get("/api/sessions")
    assert response.status_code == 200
    data = response.json()
    assert "sessions" in data
    assert "current" in data

def test_files_tree_endpoint():
    response = client.get("/api/files/tree")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)

def test_tasks_endpoint():
    response = client.get("/api/tasks")
    assert response.status_code == 200
    data = response.json()
    assert "todo" in data
    assert "done" in data


def test_sessions_tree_endpoint():
    response = client.get("/api/v1/sessions/tree")
    assert response.status_code == 200
    data = response.json()
    assert "persistent_sessions" in data
    assert "ephemeral_sessions" in data
    assert "total_sessions" in data


def test_mailbox_queue_endpoint():
    response = client.get("/api/v1/mailbox/queue")
    assert response.status_code == 200
    data = response.json()
    assert "priority_breakdown" in data
    assert "total_messages" in data
    assert "mailboxes" in data


def test_background_tasks_endpoint():
    response = client.get("/api/v1/tasks/background")
    assert response.status_code == 200
    data = response.json()
    assert "total_tasks" in data
    assert "running" in data
    assert "tasks" in data


# ─── Ágora Endpoints Tests ────────────────────────────────────

def test_agora_threads_endpoint():
    response = client.get("/api/agora/threads")
    assert response.status_code == 200
    data = response.json()
    assert "threads" in data
    assert isinstance(data["threads"], list)


def test_agora_personas_endpoint():
    response = client.get("/api/agora/personas")
    assert response.status_code == 200
    data = response.json()
    assert "personas" in data
    assert isinstance(data["personas"], list)
    # Check that canonical personas exist
    persona_ids = [p["id"] for p in data["personas"]]
    assert "tiny_steward" in persona_ids
    assert "whisper_owl" in persona_ids


def test_agora_post_and_retrieve_message():
    thread_slug = "test_thread_api"
    # Create or post message
    post_res = client.post(f"/api/agora/threads/{thread_slug}/messages", json={
        "author_id": "human",
        "content": "Testing Agora API message posting from test suite.",
    })
    assert post_res.status_code == 200
    msg_data = post_res.json()
    assert msg_data["status"] == "ok"
    assert msg_data["message"]["author_id"] == "human"

    # Retrieve messages
    get_res = client.get(f"/api/agora/threads/{thread_slug}")
    assert get_res.status_code == 200
    t_data = get_res.json()
    assert t_data["slug"] == thread_slug
    assert len(t_data["messages"]) >= 1


def test_agora_propose_and_approve_persona():
    prop_res = client.post("/api/agora/personas/propose", json={
        "proposer_id": "whisper_owl",
        "persona": {
            "id": "test_recruit_api",
            "name": "Test Recruit",
            "emoji": "🧪",
            "archetype": "Analista de Pruebas",
            "assigned_skill_domains": ["compliance_and_grc", "file_utilities"],
        },
        "justification": "Necesitamos un agente para pruebas continuas de API.",
    })
    assert prop_res.status_code == 200
    prop_data = prop_res.json()
    assert prop_data["status"] == "ok"
    assert prop_data["proposal"]["status"] == "pending_approval"

    # Approve persona
    app_res = client.post("/api/agora/personas/approve", json={
        "approver_id": "tiny_steward",
        "persona": prop_data["proposal"]["persona"],
    })
    assert app_res.status_code == 200
    app_data = app_res.json()
    assert app_data["status"] == "ok"
    assert app_data["persona"]["id"] == "test_recruit_api"

    # Cleanup test persona file so it does not pollute the factory roster
    test_file = Path("agora/personas/test_recruit_api.json")
    if test_file.exists():
        test_file.unlink()


def test_agora_worker_evaluations_endpoints():
    get_res = client.get("/api/agora/workers/evaluations")
    assert get_res.status_code == 200
    data = get_res.json()
    assert "evaluations" in data
    assert "whisper_owl" in data["evaluations"]

    # Evaluate worker
    eval_res = client.post("/api/agora/workers/evaluate", json={
        "worker_id": "whisper_owl",
        "evaluator_id": "tiny_steward",
        "score": 96,
        "rating": "A+",
        "feedback": "Auditorías DevSecOps impecables.",
        "current_focus": "Repositorios de electrónica maker y ESP32.",
    })
    assert eval_res.status_code == 200
    res_data = eval_res.json()
    assert res_data["status"] == "ok"
    assert res_data["evaluation"]["score"] == 96
    assert res_data["evaluation"]["rating"] == "A+"


def test_agora_mission_endpoints():
    # Propose mission
    prop_res = client.post("/api/agora/missions/propose", json={
        "thread_slug": "autofinanciacion_y_hardware",
        "proposer_id": "craft_fox",
        "mission": {
            "title": "Carcasas Modulares DIN para ESP32",
            "target_revenue_eur": 360,
            "pricing_eur": 18,
            "deliverables": ["Archivos STL", "Archivos STEP"],
            "payment_channels": ["BTC", "XMR"],
        },
    })
    assert prop_res.status_code == 200
    prop_data = prop_res.json()
    assert prop_data["status"] == "ok"
    mission_id = prop_data["proposal"]["id"]

    # Steer mission
    steer_res = client.post("/api/agora/missions/steer", json={
        "thread_slug": "autofinanciacion_y_hardware",
        "mission_id": mission_id,
        "steerer_id": "tiny_steward",
        "feedback": "Prohibidos envíos físicos. Exclusivo STL digital.",
        "required_changes": ["Formato .zip", "Descarga inmediata"],
    })
    assert steer_res.status_code == 200
    steer_data = steer_res.json()
    assert steer_data["status"] == "ok"

    # Approve mission
    app_res = client.post("/api/agora/missions/approve", json={
        "thread_slug": "autofinanciacion_y_hardware",
        "mission_id": mission_id,
        "approver_id": "tiny_steward",
        "comments": "Misión autorizada para ejecución.",
    })
    assert app_res.status_code == 200
    app_data = app_res.json()
    assert app_data["status"] == "ok"


def test_agora_dispatcher_endpoints():
    # Check status
    st_res = client.get("/api/agora/dispatcher/status")
    assert st_res.status_code == 200
    st_data = st_res.json()
    assert "running" in st_data
    assert "active_threads" in st_data

    # Start dispatcher with fast interval for test
    start_res = client.post("/api/agora/dispatcher/start", json={
        "interval_s": 5.0,
        "threads": ["autoorganizacion_y_roles"],
    })
    assert start_res.status_code == 200
    start_data = start_res.json()
    assert start_data["dispatcher"]["running"] is True

    # Stop dispatcher
    stop_res = client.post("/api/agora/dispatcher/stop")
    assert stop_res.status_code == 200
    stop_data = stop_res.json()
    assert stop_data["dispatcher"]["running"] is False


def test_chat_history_and_stream():
    # Fetch history
    h_res = client.get("/api/chat/history?session=default")
    assert h_res.status_code == 200
    h_data = h_res.json()
    assert "messages" in h_data
    assert h_data["session"] == "default"

    # Test stream endpoint
    s_res = client.post("/api/chat/stream", json={"prompt": "Hola Tiny Steward", "session": "default"})
    assert s_res.status_code == 200
    assert "text/event-stream" in s_res.headers["content-type"]
    text = s_res.text
    assert "data: " in text
    assert "[DONE]" in text


def test_tasks_crud_and_parser():
    # Create task
    c_res = client.post("/api/tasks/create", json={"title": "Test Operativo Automatizado", "status": "todo", "session": "default"})
    assert c_res.status_code == 200
    c_data = c_res.json()
    assert c_data["status"] == "todo"

    # Get tasks
    g_res = client.get("/api/tasks?session=default")
    assert g_res.status_code == 200
    g_data = g_res.json()
    assert "columns" in g_data
    assert any("Test Operativo Automatizado" in t["title"] for t in g_data["columns"]["todo"])

    # Update task
    u_res = client.post("/api/tasks/update", json={"task_id": "Test Operativo Automatizado", "status": "done", "session": "default"})
    assert u_res.status_code == 200


def test_files_crud_endpoints():
    test_path = "scratch_test_file.txt"
    # Create file
    c_res = client.post("/api/files/create", json={"path": test_path, "is_dir": False, "initial_content": "Prueba de archivo"})
    assert c_res.status_code == 200

    # Get content
    g_res = client.get(f"/api/files/content?path={test_path}")
    assert g_res.status_code == 200
    assert g_res.json()["content"] == "Prueba de archivo"

    # Delete file
    d_res = client.post("/api/files/delete", json={"path": test_path})
    assert d_res.status_code == 200


def test_graph_inspect_and_rebuild():
    r_res = client.post("/api/graph/rebuild")
    assert r_res.status_code == 200
    r_data = r_res.json()
    assert "total_nodes" in r_data

    i_res = client.get("/api/graph/inspect?id=topic:general")
    assert i_res.status_code == 200
    i_data = i_res.json()
    assert "id" in i_data


def test_mailbox_send_endpoint():
    s_res = client.post("/api/v1/mailbox/send", json={
        "from_session": "test_sender",
        "to_session": "default",
        "content": "Notificación de prueba",
        "priority": "high"
    })
    assert s_res.status_code == 200
    assert "message_id" in s_res.json()


def test_factory_orders_list_and_patch():
    # List orders
    l_res = client.get("/api/factory/orders/list")
    assert l_res.status_code == 200
    l_data = l_res.json()
    assert "stats" in l_data
    assert "orders" in l_data
    assert "total_revenue_eur" in l_data["stats"]

    # Place temporary order to test patch
    ord_id = f"test_ord_{int(time.time()*1000)}"
    client.post("/api/factory/orders", json={
        "order_id": ord_id,
        "product": {"title": "Test Jarrón", "total": 29.50},
        "customer": {"name": "Test Cliente", "email": "test@example.com"},
        "created_at": "2026-09-27T12:00:00",
        "status": "pending",
        "payment_wallets": {"xmr": "test_wallet"}
    })

    # Update status
    p_res = client.patch(f"/api/factory/orders/{ord_id}/status", json={
        "status": "in_print",
        "carrier": "Correos Express",
        "tracking_code": "CX123456789ES",
        "operator_notes": "Imprimiendo en PLA Negro"
    })
    assert p_res.status_code == 200
    p_data = p_res.json()
    assert p_data["new_status"] == "in_print"

    # Cleanup test order file
    test_ord_file = Path(f"fabrica/orders/{ord_id}.json")
    if test_ord_file.exists():
        test_ord_file.unlink()




