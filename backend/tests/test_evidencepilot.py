"""
EvidencePilot AI - Backend API Tests
Tests all CRUD operations, file upload, logic tree, AI analysis, settings, dashboard, and export endpoints.
"""
import pytest
import requests
import os
import time
import tempfile

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test data
TEST_CASE_TITLE = "TEST_Auth_SAML_Issue_Blank_Page"
TEST_CATEGORY_ID = "auth_saml"
TEST_FILE_CONTENT = "portal sharing/rest token validation failed\n2026-01-15 10:32:45 EST ERROR: SAML assertion expired"

class TestHealthAndCategories:
    """Test health check and categories endpoints"""
    
    def test_api_root(self):
        """GET /api/ returns status ok"""
        response = requests.get(f"{BASE_URL}/api/")
        assert response.status_code == 200
        data = response.json()
        assert data["app"] == "EvidencePilot AI"
        assert data["status"] == "ok"
        print(f"✓ API root: {data}")
    
    def test_get_categories(self):
        """GET /api/categories returns 10 categories + layers + context_fields"""
        response = requests.get(f"{BASE_URL}/api/categories")
        assert response.status_code == 200
        data = response.json()
        
        # Verify categories
        assert "categories" in data
        assert len(data["categories"]) == 10, f"Expected 10 categories, got {len(data['categories'])}"
        
        # Verify layers
        assert "layers" in data
        assert len(data["layers"]) >= 7, f"Expected at least 7 layers, got {len(data['layers'])}"
        
        # Verify context_fields
        assert "context_fields" in data
        assert len(data["context_fields"]) >= 8, f"Expected at least 8 context fields"
        
        # Check specific category exists
        cat_ids = [c["id"] for c in data["categories"]]
        assert "auth_saml" in cat_ids
        assert "web_tier" in cat_ids
        assert "pro_crash" in cat_ids
        print(f"✓ Categories: {len(data['categories'])} categories, {len(data['layers'])} layers, {len(data['context_fields'])} context fields")
    
    def test_get_logic_tree_auth_saml(self):
        """GET /api/categories/auth_saml/logic-tree returns tree"""
        response = requests.get(f"{BASE_URL}/api/categories/auth_saml/logic-tree")
        assert response.status_code == 200
        data = response.json()
        assert data["category_id"] == "auth_saml"
        assert "tree" in data
        assert len(data["tree"]) >= 3, "auth_saml should have at least 3 questions"
        print(f"✓ auth_saml logic tree: {len(data['tree'])} questions")
    
    def test_get_logic_tree_web_tier(self):
        """GET /api/categories/web_tier/logic-tree returns tree"""
        response = requests.get(f"{BASE_URL}/api/categories/web_tier/logic-tree")
        assert response.status_code == 200
        data = response.json()
        assert data["category_id"] == "web_tier"
        assert "tree" in data
        assert len(data["tree"]) >= 2
        print(f"✓ web_tier logic tree: {len(data['tree'])} questions")
    
    def test_get_logic_tree_pro_crash(self):
        """GET /api/categories/pro_crash/logic-tree returns tree"""
        response = requests.get(f"{BASE_URL}/api/categories/pro_crash/logic-tree")
        assert response.status_code == 200
        data = response.json()
        assert data["category_id"] == "pro_crash"
        assert "tree" in data
        assert len(data["tree"]) >= 3
        print(f"✓ pro_crash logic tree: {len(data['tree'])} questions")
    
    def test_get_logic_tree_default_fallback(self):
        """GET /api/categories/unknown_category/logic-tree returns default tree"""
        response = requests.get(f"{BASE_URL}/api/categories/unknown_category/logic-tree")
        assert response.status_code == 200
        data = response.json()
        assert data["category_id"] == "unknown_category"
        assert "tree" in data
        # Should return default tree
        assert len(data["tree"]) >= 3
        print(f"✓ Default fallback logic tree: {len(data['tree'])} questions")


class TestCaseCRUD:
    """Test case CRUD operations"""
    
    @pytest.fixture(autouse=True)
    def setup_and_teardown(self):
        """Setup and cleanup test cases"""
        self.created_case_ids = []
        yield
        # Cleanup
        for case_id in self.created_case_ids:
            try:
                requests.delete(f"{BASE_URL}/api/cases/{case_id}")
            except:
                pass
    
    def test_create_case(self):
        """POST /api/cases creates a case with correct structure"""
        payload = {
            "title": TEST_CASE_TITLE,
            "category_id": TEST_CATEGORY_ID,
            "context": {
                "summary": "User sees blank page after SAML sign-in",
                "timestamps": "2026-01-15 10:32 EST",
                "urls": "https://gis.example.com/portal",
                "versions": "Enterprise 11.3",
                "topology": "Single machine deployment",
                "recent_changes": "Updated SAML cert last week",
                "repro_steps": "1. Go to portal 2. Click sign in 3. Blank page",
                "already_tested": "Cleared cache",
                "environment_notes": "Behind corporate proxy"
            },
            "symptom_clues": ["blank page after sign in", "redirect loop"]
        }
        response = requests.post(f"{BASE_URL}/api/cases", json=payload)
        assert response.status_code == 200, f"Create case failed: {response.text}"
        data = response.json()
        
        # Verify structure
        assert "id" in data
        assert data["status"] == "open"
        assert data["title"] == TEST_CASE_TITLE
        assert data["category_id"] == TEST_CATEGORY_ID
        assert "ai_results" in data
        assert data["ai_results"]["provider_a"] is None
        assert data["ai_results"]["provider_b"] is None
        
        self.created_case_ids.append(data["id"])
        print(f"✓ Created case: {data['id']}")
        return data["id"]
    
    def test_list_cases(self):
        """GET /api/cases lists cases with score field"""
        # First create a case
        payload = {"title": "TEST_List_Case", "category_id": "auth_saml"}
        create_resp = requests.post(f"{BASE_URL}/api/cases", json=payload)
        case_id = create_resp.json()["id"]
        self.created_case_ids.append(case_id)
        
        # List cases
        response = requests.get(f"{BASE_URL}/api/cases")
        assert response.status_code == 200
        data = response.json()
        assert "cases" in data
        
        # Find our case and verify score
        our_case = next((c for c in data["cases"] if c["id"] == case_id), None)
        assert our_case is not None, "Created case not found in list"
        assert "score" in our_case
        assert "overall_pct" in our_case["score"]
        print(f"✓ Listed cases: {len(data['cases'])} cases, score present")
    
    def test_get_case(self):
        """GET /api/cases/{id} returns case with score"""
        # Create case
        payload = {"title": "TEST_Get_Case", "category_id": "web_tier"}
        create_resp = requests.post(f"{BASE_URL}/api/cases", json=payload)
        case_id = create_resp.json()["id"]
        self.created_case_ids.append(case_id)
        
        # Get case
        response = requests.get(f"{BASE_URL}/api/cases/{case_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == case_id
        assert "score" in data
        assert "overall_pct" in data["score"]
        assert "readiness" in data["score"]
        print(f"✓ Got case: {case_id}, score: {data['score']['overall_pct']}%")
    
    def test_update_case(self):
        """PATCH /api/cases/{id} updates context, title, status"""
        # Create case
        payload = {"title": "TEST_Update_Case", "category_id": "portal_ops"}
        create_resp = requests.post(f"{BASE_URL}/api/cases", json=payload)
        case_id = create_resp.json()["id"]
        self.created_case_ids.append(case_id)
        
        # Update case
        update_payload = {
            "title": "TEST_Updated_Title",
            "status": "resolved",
            "context": {
                "summary": "Updated summary",
                "timestamps": "2026-01-16 14:00 PST"
            }
        }
        response = requests.patch(f"{BASE_URL}/api/cases/{case_id}", json=update_payload)
        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "TEST_Updated_Title"
        assert data["status"] == "resolved"
        assert data["context"]["summary"] == "Updated summary"
        print(f"✓ Updated case: {case_id}")
    
    def test_delete_case(self):
        """DELETE /api/cases/{id} cleans up"""
        # Create case
        payload = {"title": "TEST_Delete_Case", "category_id": "datastore"}
        create_resp = requests.post(f"{BASE_URL}/api/cases", json=payload)
        case_id = create_resp.json()["id"]
        
        # Delete case
        response = requests.delete(f"{BASE_URL}/api/cases/{case_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["deleted"] == case_id
        
        # Verify deleted
        get_resp = requests.get(f"{BASE_URL}/api/cases/{case_id}")
        assert get_resp.status_code == 404
        print(f"✓ Deleted case: {case_id}")


class TestFileOperations:
    """Test file upload and management"""
    
    @pytest.fixture(autouse=True)
    def setup_and_teardown(self):
        """Setup and cleanup"""
        self.created_case_ids = []
        yield
        for case_id in self.created_case_ids:
            try:
                requests.delete(f"{BASE_URL}/api/cases/{case_id}")
            except:
                pass
    
    def test_upload_file_with_layer_detection(self):
        """POST /api/cases/{id}/files uploads file and auto-detects layer"""
        # Create case
        payload = {"title": "TEST_File_Upload", "category_id": "auth_saml"}
        create_resp = requests.post(f"{BASE_URL}/api/cases", json=payload)
        case_id = create_resp.json()["id"]
        self.created_case_ids.append(case_id)
        
        # Create temp file with portal content
        with tempfile.NamedTemporaryFile(mode='w', suffix='.log', delete=False) as f:
            f.write(TEST_FILE_CONTENT)
            temp_path = f.name
        
        try:
            # Upload file named portal.log
            with open(temp_path, 'rb') as f:
                files = {'files': ('portal.log', f, 'text/plain')}
                response = requests.post(f"{BASE_URL}/api/cases/{case_id}/files", files=files)
            
            assert response.status_code == 200, f"Upload failed: {response.text}"
            data = response.json()
            assert "uploaded" in data
            assert len(data["uploaded"]) == 1
            
            # Verify layer auto-detection (should detect 'portal' from filename/content)
            uploaded_file = data["uploaded"][0]
            assert "id" in uploaded_file
            assert "layer" in uploaded_file
            assert uploaded_file["layer"] == "portal", f"Expected 'portal' layer, got '{uploaded_file['layer']}'"
            print(f"✓ Uploaded file: {uploaded_file['name']}, layer: {uploaded_file['layer']}")
        finally:
            os.unlink(temp_path)
    
    def test_update_file_layer(self):
        """PATCH /api/cases/{id}/files/{fid} changes layer"""
        # Create case and upload file
        payload = {"title": "TEST_File_Layer", "category_id": "auth_saml"}
        create_resp = requests.post(f"{BASE_URL}/api/cases", json=payload)
        case_id = create_resp.json()["id"]
        self.created_case_ids.append(case_id)
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.log', delete=False) as f:
            f.write("test content")
            temp_path = f.name
        
        try:
            with open(temp_path, 'rb') as f:
                files = {'files': ('test.log', f, 'text/plain')}
                upload_resp = requests.post(f"{BASE_URL}/api/cases/{case_id}/files", files=files)
            
            file_id = upload_resp.json()["uploaded"][0]["id"]
            
            # Update layer
            response = requests.patch(
                f"{BASE_URL}/api/cases/{case_id}/files/{file_id}",
                data={"layer": "web_tier"}
            )
            assert response.status_code == 200
            data = response.json()
            assert data["layer"] == "web_tier"
            print(f"✓ Updated file layer to: {data['layer']}")
        finally:
            os.unlink(temp_path)
    
    def test_preview_file(self):
        """GET /api/cases/{id}/files/{fid}/preview returns text"""
        # Create case and upload file
        payload = {"title": "TEST_File_Preview", "category_id": "auth_saml"}
        create_resp = requests.post(f"{BASE_URL}/api/cases", json=payload)
        case_id = create_resp.json()["id"]
        self.created_case_ids.append(case_id)
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.log', delete=False) as f:
            f.write(TEST_FILE_CONTENT)
            temp_path = f.name
        
        try:
            with open(temp_path, 'rb') as f:
                files = {'files': ('preview_test.log', f, 'text/plain')}
                upload_resp = requests.post(f"{BASE_URL}/api/cases/{case_id}/files", files=files)
            
            file_id = upload_resp.json()["uploaded"][0]["id"]
            
            # Preview file
            response = requests.get(f"{BASE_URL}/api/cases/{case_id}/files/{file_id}/preview")
            assert response.status_code == 200
            data = response.json()
            assert "text" in data
            assert "portal sharing/rest" in data["text"]
            print(f"✓ File preview: {len(data['text'])} chars")
        finally:
            os.unlink(temp_path)


class TestLogicTree:
    """Test logic tree save functionality"""
    
    @pytest.fixture(autouse=True)
    def setup_and_teardown(self):
        self.created_case_ids = []
        yield
        for case_id in self.created_case_ids:
            try:
                requests.delete(f"{BASE_URL}/api/cases/{case_id}")
            except:
                pass
    
    def test_save_logic_answers(self):
        """POST /api/cases/{id}/logic saves logic answers and returns case"""
        # Create case
        payload = {"title": "TEST_Logic_Tree", "category_id": "auth_saml"}
        create_resp = requests.post(f"{BASE_URL}/api/cases", json=payload)
        case_id = create_resp.json()["id"]
        self.created_case_ids.append(case_id)
        
        # Save logic answers
        answers = [
            {"node_id": "blank", "question": "Is the user seeing a blank page or a redirect loop after sign-in?", "answer_value": "blank", "answer_label": "Blank page"},
            {"node_id": "vanity", "question": "Does the failure happen ONLY via the vanity / custom domain?", "answer_value": "vanity_only", "answer_label": "Yes (vanity-only)"},
            {"node_id": "har", "question": "Do you have a HAR captured with 'Preserve log' enabled across the failed login?", "answer_value": "yes", "answer_label": "Yes"}
        ]
        response = requests.post(f"{BASE_URL}/api/cases/{case_id}/logic", json=answers)
        assert response.status_code == 200
        data = response.json()
        assert "logic_answers" in data
        assert len(data["logic_answers"]) == 3
        assert "score" in data
        print(f"✓ Saved logic answers: {len(data['logic_answers'])} answers")


class TestScore:
    """Test evidence scoring"""
    
    @pytest.fixture(autouse=True)
    def setup_and_teardown(self):
        self.created_case_ids = []
        yield
        for case_id in self.created_case_ids:
            try:
                requests.delete(f"{BASE_URL}/api/cases/{case_id}")
            except:
                pass
    
    def test_get_score(self):
        """GET /api/cases/{id}/score returns completeness metrics"""
        # Create case with context
        payload = {
            "title": "TEST_Score",
            "category_id": "auth_saml",
            "context": {
                "timestamps": "2026-01-15 10:32 EST",
                "urls": "https://gis.example.com/portal",
                "versions": "Enterprise 11.3",
                "topology": "Single machine",
                "recent_changes": "Cert update",
                "repro_steps": "1. Sign in 2. Blank page"
            }
        }
        create_resp = requests.post(f"{BASE_URL}/api/cases", json=payload)
        case_id = create_resp.json()["id"]
        self.created_case_ids.append(case_id)
        
        # Get score
        response = requests.get(f"{BASE_URL}/api/cases/{case_id}/score")
        assert response.status_code == 200
        data = response.json()
        
        assert "context_pct" in data
        assert "layer_pct" in data
        assert "overall_pct" in data
        assert "readiness" in data
        assert "gaps" in data or "context_gaps" in data
        print(f"✓ Score: context={data['context_pct']}%, layer={data['layer_pct']}%, overall={data['overall_pct']}%, readiness={data['readiness']}")


class TestAIAnalysis:
    """Test AI analysis endpoint - uses real Emergent LLM key"""
    
    @pytest.fixture(autouse=True)
    def setup_and_teardown(self):
        self.created_case_ids = []
        yield
        for case_id in self.created_case_ids:
            try:
                requests.delete(f"{BASE_URL}/api/cases/{case_id}")
            except:
                pass
    
    def test_analyze_dual_providers(self):
        """POST /api/cases/{id}/analyze with both providers returns output from BOTH (async with polling)"""
        # Create case with context
        payload = {
            "title": "TEST_AI_Analysis",
            "category_id": "auth_saml",
            "context": {
                "summary": "User sees blank page after SAML sign-in via vanity URL",
                "timestamps": "2026-01-15 10:32 EST",
                "urls": "https://gis.example.com/portal/sharing/rest",
                "versions": "Enterprise 11.3, Web Adaptor 11.3",
                "topology": "Portal + Server + Web Adaptor behind IIS",
                "recent_changes": "Updated SAML certificate last Tuesday",
                "repro_steps": "1. Go to vanity URL 2. Click sign in 3. Redirected to IdP 4. After auth, blank page"
            }
        }
        create_resp = requests.post(f"{BASE_URL}/api/cases", json=payload)
        case_id = create_resp.json()["id"]
        self.created_case_ids.append(case_id)
        
        # Upload a test file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.log', delete=False) as f:
            f.write(TEST_FILE_CONTENT)
            temp_path = f.name
        
        try:
            with open(temp_path, 'rb') as f:
                files = {'files': ('portal.log', f, 'text/plain')}
                requests.post(f"{BASE_URL}/api/cases/{case_id}/files", files=files)
        finally:
            os.unlink(temp_path)
        
        # Wait for background indexing
        time.sleep(4)
        
        # Run AI analysis (now async - returns immediately with status='running')
        response = requests.post(
            f"{BASE_URL}/api/cases/{case_id}/analyze",
            json={"use_provider_a": True, "use_provider_b": True},
            timeout=30
        )
        assert response.status_code == 200, f"Analyze failed: {response.text}"
        data = response.json()
        assert data.get("status") == "running", f"Expected status='running', got {data}"
        print(f"✓ Analysis started: {data}")
        
        # Poll for completion (max 3 minutes)
        deadline = time.time() + 180
        while time.time() < deadline:
            time.sleep(5)
            status_resp = requests.get(f"{BASE_URL}/api/cases/{case_id}/analyze/status")
            if status_resp.status_code == 200:
                status = status_resp.json()
                if status.get("status") == "done":
                    print(f"✓ Analysis completed")
                    break
        
        # Get case with results
        case_resp = requests.get(f"{BASE_URL}/api/cases/{case_id}")
        assert case_resp.status_code == 200
        case_data = case_resp.json()
        ai_results = case_data.get("ai_results", {})
        
        assert ai_results.get("ran_at") is not None, "AI analysis did not complete"
        
        provider_a = ai_results.get("provider_a")
        provider_b = ai_results.get("provider_b")
        
        assert provider_a is not None, "Provider A result missing"
        assert provider_b is not None, "Provider B result missing"
        
        # Check for errors
        if provider_a.get("error"):
            print(f"⚠ Provider A error: {provider_a['error']}")
        else:
            assert provider_a.get("output") is not None, "Provider A output missing"
            print(f"✓ Provider A: {provider_a.get('provider_label')} - {provider_a.get('model')}")
        
        if provider_b.get("error"):
            print(f"⚠ Provider B error: {provider_b['error']}")
        else:
            assert provider_b.get("output") is not None, "Provider B output missing"
            print(f"✓ Provider B: {provider_b.get('provider_label')} - {provider_b.get('model')}")
        
        # Verify disagreement computed
        disagreement = ai_results.get("disagreement")
        assert disagreement is not None, "Disagreement not computed"
        assert "layer_agreement" in disagreement
        print(f"✓ Disagreement: layer_agreement={disagreement.get('layer_agreement')}, delta={disagreement.get('confidence_delta')}")
        
        # Verify retrieval metadata (new RAG feature)
        retrieval = ai_results.get("retrieval")
        assert retrieval is not None, "Retrieval metadata missing"
        assert "top_k" in retrieval
        assert "chunks" in retrieval
        print(f"✓ Retrieval: top_k={retrieval['top_k']}, chunks={len(retrieval['chunks'])}")


class TestExport:
    """Test export endpoints"""
    
    @pytest.fixture(autouse=True)
    def setup_and_teardown(self):
        self.created_case_ids = []
        yield
        for case_id in self.created_case_ids:
            try:
                requests.delete(f"{BASE_URL}/api/cases/{case_id}")
            except:
                pass
    
    def test_export_markdown(self):
        """GET /api/cases/{id}/export?format=markdown returns markdown"""
        payload = {"title": "TEST_Export_MD", "category_id": "auth_saml"}
        create_resp = requests.post(f"{BASE_URL}/api/cases", json=payload)
        case_id = create_resp.json()["id"]
        self.created_case_ids.append(case_id)
        
        response = requests.get(f"{BASE_URL}/api/cases/{case_id}/export?format=markdown")
        assert response.status_code == 200
        assert "text/markdown" in response.headers.get("Content-Type", "")
        assert "# EvidencePilot Report" in response.text
        print(f"✓ Export markdown: {len(response.text)} chars")
    
    def test_export_json(self):
        """GET /api/cases/{id}/export?format=json returns JSON"""
        payload = {"title": "TEST_Export_JSON", "category_id": "auth_saml"}
        create_resp = requests.post(f"{BASE_URL}/api/cases", json=payload)
        case_id = create_resp.json()["id"]
        self.created_case_ids.append(case_id)
        
        response = requests.get(f"{BASE_URL}/api/cases/{case_id}/export?format=json")
        assert response.status_code == 200
        assert "application/json" in response.headers.get("Content-Type", "")
        data = response.json()
        assert "case" in data
        assert "evidence_score" in data
        print(f"✓ Export JSON: {len(response.text)} chars")
    
    def test_export_html(self):
        """GET /api/cases/{id}/export?format=html returns HTML"""
        payload = {"title": "TEST_Export_HTML", "category_id": "auth_saml"}
        create_resp = requests.post(f"{BASE_URL}/api/cases", json=payload)
        case_id = create_resp.json()["id"]
        self.created_case_ids.append(case_id)
        
        response = requests.get(f"{BASE_URL}/api/cases/{case_id}/export?format=html")
        assert response.status_code == 200
        assert "text/html" in response.headers.get("Content-Type", "")
        assert "<!doctype html>" in response.text.lower()
        print(f"✓ Export HTML: {len(response.text)} chars")


class TestSettings:
    """Test settings endpoints"""
    
    def test_get_settings(self):
        """GET /api/settings returns masked api keys"""
        response = requests.get(f"{BASE_URL}/api/settings")
        assert response.status_code == 200
        data = response.json()
        
        # Verify structure
        assert "provider_a_label" in data
        assert "provider_b_label" in data
        assert "retention_days" in data
        assert "max_upload_mb" in data
        assert "escalation_contact" in data
        
        # Verify API keys are masked (contain •)
        if data.get("provider_a_api_key"):
            assert "•" in data["provider_a_api_key"] or data["provider_a_api_key"] == ""
        if data.get("provider_b_api_key"):
            assert "•" in data["provider_b_api_key"] or data["provider_b_api_key"] == ""
        
        print(f"✓ Settings: retention={data['retention_days']} days, max_upload={data['max_upload_mb']}MB")
    
    def test_update_settings(self):
        """PUT /api/settings updates and persists"""
        # Get current settings
        current = requests.get(f"{BASE_URL}/api/settings").json()
        
        # Update settings
        new_retention = 45
        payload = {
            "provider_a_label": current.get("provider_a_label", "OpenAI GPT-5.2"),
            "provider_a_model": current.get("provider_a_model", "gpt-5.2"),
            "provider_a_provider": current.get("provider_a_provider", "openai"),
            "provider_b_label": current.get("provider_b_label", "Claude Sonnet 4.5"),
            "provider_b_model": current.get("provider_b_model", "claude-sonnet-4-5-20250929"),
            "provider_b_provider": current.get("provider_b_provider", "anthropic"),
            "retention_days": new_retention,
            "max_upload_mb": current.get("max_upload_mb", 50),
            "escalation_contact": "test@example.com"
        }
        response = requests.put(f"{BASE_URL}/api/settings", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["retention_days"] == new_retention
        assert data["escalation_contact"] == "test@example.com"
        
        # Verify persistence
        verify = requests.get(f"{BASE_URL}/api/settings").json()
        assert verify["retention_days"] == new_retention
        
        # Restore original
        payload["retention_days"] = current.get("retention_days", 30)
        payload["escalation_contact"] = current.get("escalation_contact", "corp.support.help@esri.ca")
        requests.put(f"{BASE_URL}/api/settings", json=payload)
        
        print(f"✓ Settings updated and persisted")


class TestDashboard:
    """Test dashboard stats endpoint"""
    
    def test_dashboard_stats(self):
        """GET /api/dashboard/stats returns all required fields"""
        response = requests.get(f"{BASE_URL}/api/dashboard/stats")
        assert response.status_code == 200
        data = response.json()
        
        assert "total" in data
        assert "open" in data
        assert "resolved" in data
        assert "analyzed" in data
        assert "avg_completeness" in data
        assert "by_category" in data
        
        print(f"✓ Dashboard stats: total={data['total']}, open={data['open']}, resolved={data['resolved']}, analyzed={data['analyzed']}, avg_completeness={data['avg_completeness']}%")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
