// MongoDB初期化スクリプト
db = db.getSiblingDB('stock_data');

print('Initializing stock_data database...');

// users コレクションのインデックス
print('Creating indexes for users collection...');
db.users.createIndex(
    { "username": 1 },
    { 
        unique: true,
        name: "username_unique",
        background: true
    }
);
db.users.createIndex(
    { "email": 1 },
    { 
        unique: true,
        name: "email_unique",
        background: true
    }
);
db.users.createIndex(
    { "role": 1, "is_active": 1 },
    { 
        name: "role_active",
        background: true
    }
);
db.users.createIndex(
    { "created_at": 1 },
    { 
        name: "created_at_1",
        background: true
    }
);

// api_keys コレクションのインデックス
print('Creating indexes for api_keys collection...');
db.api_keys.createIndex(
    { "key_id": 1 },
    { 
        unique: true,
        name: "key_id_unique",
        background: true
    }
);
db.api_keys.createIndex(
    { "user_id": 1, "is_active": 1 },
    { 
        name: "user_id_active",
        background: true
    }
);
db.api_keys.createIndex(
    { "expires_at": 1 },
    { 
        name: "expires_at_1",
        background: true,
        expireAfterSeconds: 0  // TTL インデックス
    }
);
db.api_keys.createIndex(
    { "last_used": 1 },
    { 
        name: "last_used_1",
        background: true
    }
);

// daily_prices コレクションのインデックス
print('Creating indexes for daily_prices collection...');
db.daily_prices.createIndex(
    { "symbol": 1, "date": 1 }, 
    { 
        unique: true,
        name: "symbol_date_unique",
        background: true
    }
);
db.daily_prices.createIndex(
    { "symbol": 1 },
    { 
        name: "symbol_1",
        background: true
    }
);
db.daily_prices.createIndex(
    { "date": 1 },
    { 
        name: "date_1",
        background: true
    }
);
// 複合インデックス（範囲クエリ用）
db.daily_prices.createIndex(
    { "symbol": 1, "date": -1 },
    { 
        name: "symbol_date_desc",
        background: true
    }
);

// stock_info コレクションのインデックス
print('Creating indexes for stock_info collection...');
db.stock_info.createIndex(
    { "symbol": 1 },
    { 
        unique: true,
        name: "symbol_unique",
        background: true
    }
);
// テキスト検索用インデックス
db.stock_info.createIndex(
    { "name": "text", "symbol": "text" },
    {
        name: "text_search",
        background: true,
        weights: { "symbol": 10, "name": 5 }
    }
);
db.stock_info.createIndex(
    { "market": 1 },
    { 
        name: "market_1",
        background: true
    }
);
// セクター・業界での検索用
db.stock_info.createIndex(
    { "sector": 1, "industry": 1 },
    { 
        name: "sector_industry",
        background: true
    }
);

// financials コレクションのインデックス
print('Creating indexes for financials collection...');
db.financials.createIndex(
    { "symbol": 1, "period_type": 1, "period_end": 1 },
    { 
        unique: true,
        name: "symbol_period_unique",
        background: true
    }
);
db.financials.createIndex(
    { "symbol": 1 },
    { 
        name: "symbol_1",
        background: true
    }
);
// 期間タイプでの検索用
db.financials.createIndex(
    { "period_type": 1, "period_end": -1 },
    { 
        name: "period_type_end_desc",
        background: true
    }
);

// コレクションレベルの設定
print('Configuring collection settings...');

// daily_prices のバリデーションスキーマ
db.createCollection("daily_prices", {
    validator: {
        $jsonSchema: {
            bsonType: "object",
            required: ["symbol", "date", "open", "high", "low", "close", "volume"],
            properties: {
                symbol: {
                    bsonType: "string",
                    description: "Stock symbol is required"
                },
                date: {
                    bsonType: "string",
                    pattern: "^[0-9]{4}-[0-9]{2}-[0-9]{2}$",
                    description: "Date must be in YYYY-MM-DD format"
                },
                open: {
                    bsonType: "double",
                    minimum: 0,
                    description: "Open price must be positive"
                },
                high: {
                    bsonType: "double",
                    minimum: 0,
                    description: "High price must be positive"
                },
                low: {
                    bsonType: "double",
                    minimum: 0,
                    description: "Low price must be positive"
                },
                close: {
                    bsonType: "double",
                    minimum: 0,
                    description: "Close price must be positive"
                },
                volume: {
                    bsonType: "int",
                    minimum: 0,
                    description: "Volume must be non-negative"
                }
            }
        }
    },
    validationLevel: "moderate",
    validationAction: "warn"
});

// デフォルト管理者ユーザーを作成
print('Creating default admin user...');
var adminExists = db.users.findOne({ "username": "admin" });

if (!adminExists) {
    // パスワード: "admin123" のハッシュ (bcrypt)
    // 本番環境では必ず変更すること!
    var adminUser = {
        username: "admin",
        email: "admin@stockdata.local",
        full_name: "System Administrator",
        role: "admin",
        is_active: true,
        is_verified: true,
        hashed_password: "$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewdBPj3cOy.g6UxC",  // admin123
        created_at: new Date(),
        updated_at: new Date(),
        rate_limit_requests: 10000,
        rate_limit_window: 3600
    };
    
    db.users.insertOne(adminUser);
    print('Default admin user created (username: admin, password: admin123)');
    print('WARNING: Change the default admin password immediately!');
} else {
    print('Default admin user already exists');
}

// 統計情報を表示
print('Database initialization completed!');
print('Collections created:');
db.getCollectionNames().forEach(function(collection) {
    var count = db.getCollection(collection).countDocuments();
    print('  ' + collection + ': ' + count + ' documents');
});

print('Indexes created:');
db.getCollectionNames().forEach(function(collection) {
    var indexes = db.getCollection(collection).getIndexes();
    print('  ' + collection + ': ' + indexes.length + ' indexes');
    indexes.forEach(function(index) {
        print('    - ' + index.name);
    });
});

print('');
print('=== SECURITY WARNING ===');
print('Default admin credentials:');
print('  Username: admin');
print('  Password: admin123');
print('CHANGE THESE CREDENTIALS IMMEDIATELY IN PRODUCTION!');
print('=========================');