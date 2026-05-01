-- 代理IP池表
CREATE TABLE IF NOT EXISTS proxy_ips (
    id INT AUTO_INCREMENT PRIMARY KEY,
    ip VARCHAR(50) NOT NULL,
    port INT NOT NULL,
    protocol VARCHAR(10) DEFAULT 'http',
    user_id INT NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    success_count INT DEFAULT 0,
    fail_count INT DEFAULT 0,
    last_used DATETIME,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

-- 代理池测试示例（从快代理获取100个代理）
-- https://dps.kdlapi.com/api/getdps/?secret_id=ouz72ft6ugmg982wel5n&signature=5ga4lsjesx046vi5r4vlswcg04uiuzbj&num=100&format=text&sep=1
