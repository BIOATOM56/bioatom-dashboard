def do_POST(self):
        clean_path = self.path.split("?")[0].rstrip("/")
        if clean_path == "/report":
            content_len = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_len)
            try:
                data = json.loads(body.decode("utf-8"))
                user = data.get("username")
                
                if user:
                    with db_lock:
                        old_data = ACCOUNTS.get(user, {})
                        old_fruits = old_data.get("fruits", [])
                        
                        if data.get("is_scan") is True:
                            new_fruits = data.get("fruits", [])
                            if not isinstance(new_fruits, list):
                                new_fruits = []
                        elif "fruits" in data and len(data["fruits"]) > 0:
                            new_fruits = data["fruits"]
                        else:
                            new_fruits = old_fruits
                        
                        ACCOUNTS[user] = {
                            "fruits": new_fruits,
                            "last_seen": time.time()
                        }
                    save_db()
                    print(f"📥 [REPORT IN] {user} | สแกนจริง: {data.get('is_scan')} | ผลไม้: {len(new_fruits)} ผล")

                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(b'{"status":"ok"}')
            except Exception as e:
                print(f"❌ [POST Error] ข้อมูลส่งมาผิดพลาด: {e} | Body: {body}")
                self.send_response(400)
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(b'{"status":"bad_request"}')
