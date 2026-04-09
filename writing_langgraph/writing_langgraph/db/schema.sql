-- =============================================
-- 小说元数据
-- =============================================
CREATE TABLE IF NOT EXISTS novel_metadata (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    genre TEXT NOT NULL,
    world_rules TEXT NOT NULL DEFAULT '{}',
    power_system_name TEXT,
    main_plot_outline TEXT NOT NULL DEFAULT '',
    theme TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =============================================
-- 战力/境界体系定义
-- =============================================
CREATE TABLE IF NOT EXISTS power_level_definition (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    novel_id INTEGER NOT NULL REFERENCES novel_metadata(id) ON DELETE CASCADE,
    level_order INTEGER NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    is_realm_boundary INTEGER DEFAULT 0
);

-- =============================================
-- 人物表
-- =============================================
CREATE TABLE IF NOT EXISTS character (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    novel_id INTEGER NOT NULL REFERENCES novel_metadata(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    alias TEXT,
    role_type TEXT NOT NULL DEFAULT 'supporting',
    core_motivation TEXT,
    core_flaw TEXT,
    arc_direction TEXT,
    current_power_level TEXT,
    current_location TEXT,
    physical_state TEXT DEFAULT '{}',
    psychological_state TEXT DEFAULT '{}',
    inventory TEXT DEFAULT '[]',
    is_active INTEGER DEFAULT 1,
    first_appearance_chapter INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =============================================
-- 人物关系（多对多）
-- =============================================
CREATE TABLE IF NOT EXISTS character_relationship (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    novel_id INTEGER NOT NULL REFERENCES novel_metadata(id) ON DELETE CASCADE,
    char_a_id INTEGER NOT NULL REFERENCES character(id) ON DELETE CASCADE,
    char_b_id INTEGER NOT NULL REFERENCES character(id) ON DELETE CASCADE,
    relationship_type TEXT NOT NULL,
    description TEXT,
    start_chapter INTEGER,
    is_active INTEGER DEFAULT 1,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(char_a_id, char_b_id, relationship_type)
);

-- =============================================
-- 道具/功法/宝物表
-- =============================================
CREATE TABLE IF NOT EXISTS item (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    novel_id INTEGER NOT NULL REFERENCES novel_metadata(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    item_type TEXT NOT NULL DEFAULT 'other',
    rarity TEXT NOT NULL DEFAULT 'common',
    owner_id INTEGER REFERENCES character(id) ON DELETE SET NULL,
    previous_owner_id INTEGER REFERENCES character(id) ON DELETE SET NULL,
    description TEXT,
    abilities TEXT DEFAULT '[]',
    origin TEXT,
    first_appearance_chapter INTEGER,
    is_active INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =============================================
-- 战力突破/变化日志
-- =============================================
CREATE TABLE IF NOT EXISTS power_change_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    novel_id INTEGER NOT NULL REFERENCES novel_metadata(id) ON DELETE CASCADE,
    character_id INTEGER NOT NULL REFERENCES character(id) ON DELETE CASCADE,
    from_level TEXT NOT NULL,
    to_level TEXT NOT NULL,
    chapter_no INTEGER NOT NULL,
    cause TEXT,
    details TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =============================================
-- 道具获得/使用日志
-- =============================================
CREATE TABLE IF NOT EXISTS item_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    novel_id INTEGER NOT NULL REFERENCES novel_metadata(id) ON DELETE CASCADE,
    item_id INTEGER NOT NULL REFERENCES item(id) ON DELETE CASCADE,
    character_id INTEGER REFERENCES character(id) ON DELETE SET NULL,
    action_type TEXT NOT NULL,
    chapter_no INTEGER NOT NULL,
    details TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =============================================
-- 伏笔/情节线表
-- =============================================
CREATE TABLE IF NOT EXISTS plot_thread (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    novel_id INTEGER NOT NULL REFERENCES novel_metadata(id) ON DELETE CASCADE,
    thread_code TEXT NOT NULL,
    title TEXT NOT NULL,
    content_summary TEXT NOT NULL,
    planted_chapter INTEGER,
    planned_resolution_chapter INTEGER,
    actual_resolution_chapter INTEGER,
    status TEXT DEFAULT 'planted',
    resolution_summary TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =============================================
-- 卷表
-- =============================================
CREATE TABLE IF NOT EXISTS volume (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    novel_id INTEGER NOT NULL REFERENCES novel_metadata(id) ON DELETE CASCADE,
    volume_order INTEGER NOT NULL,
    title TEXT NOT NULL,
    outline TEXT,
    start_chapter INTEGER NOT NULL,
    end_chapter INTEGER,
    status TEXT DEFAULT 'planning',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =============================================
-- 章节表
-- =============================================
CREATE TABLE IF NOT EXISTS chapter (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    novel_id INTEGER NOT NULL REFERENCES novel_metadata(id) ON DELETE CASCADE,
    volume_id INTEGER REFERENCES volume(id) ON DELETE SET NULL,
    chapter_order INTEGER NOT NULL,
    title TEXT,
    brief TEXT,
    plan TEXT,
    draft TEXT,
    word_count INTEGER,
    score REAL,
    status TEXT DEFAULT 'pending',
    generation_config TEXT DEFAULT '{}',
    parent_chapter_id INTEGER REFERENCES chapter(id) ON DELETE SET NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(volume_id, chapter_order)
);

-- =============================================
-- 全局记忆（世界观/战力/人物模板/主线伏笔）
-- =============================================
CREATE TABLE IF NOT EXISTS memory_global (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    novel_id INTEGER NOT NULL REFERENCES novel_metadata(id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    version INTEGER DEFAULT 1,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =============================================
-- 卷级记忆
-- =============================================
CREATE TABLE IF NOT EXISTS memory_volume (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    novel_id INTEGER NOT NULL REFERENCES novel_metadata(id) ON DELETE CASCADE,
    volume_id INTEGER NOT NULL REFERENCES volume(id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    version INTEGER DEFAULT 1,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =============================================
-- 章节级记忆（仅当前章节写作时使用）
-- =============================================
CREATE TABLE IF NOT EXISTS memory_chapter (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    novel_id INTEGER NOT NULL REFERENCES novel_metadata(id) ON DELETE CASCADE,
    chapter_id INTEGER NOT NULL REFERENCES chapter(id) ON DELETE CASCADE,
    iteration INTEGER NOT NULL,
    content TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =============================================
-- 网文套路模板
-- =============================================
CREATE TABLE IF NOT EXISTS trope_template (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    novel_id INTEGER NOT NULL REFERENCES novel_metadata(id) ON DELETE CASCADE,
    trope_type TEXT NOT NULL,
    template_name TEXT NOT NULL,
    trigger_condition TEXT,
    typical_arc TEXT,
    key_beat_sequence TEXT DEFAULT '[]',
    example_summary TEXT,
    usage_count INTEGER DEFAULT 0,
    last_used_chapter INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =============================================
-- 并行写作任务追踪
-- =============================================
CREATE TABLE IF NOT EXISTS parallel_task (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    novel_id INTEGER NOT NULL REFERENCES novel_metadata(id) ON DELETE CASCADE,
    parent_chapter_id INTEGER REFERENCES chapter(id) ON DELETE CASCADE,
    child_chapter_id INTEGER REFERENCES chapter(id) ON DELETE CASCADE,
    task_type TEXT NOT NULL,
    status TEXT DEFAULT 'pending',
    context_snapshot TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =============================================
-- 全局状态一致性锁（用于并行协调）
-- =============================================
CREATE TABLE IF NOT EXISTS global_state_lock (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    novel_id INTEGER NOT NULL REFERENCES novel_metadata(id) ON DELETE CASCADE,
    lock_type TEXT NOT NULL,
    locked_resource TEXT NOT NULL,
    locked_by_task TEXT,
    acquired_at TIMESTAMP,
    released_at TIMESTAMP
);

-- =============================================
-- 小故事追踪（用于重启后恢复规划状态）
-- =============================================
CREATE TABLE IF NOT EXISTS small_story_tracking (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    novel_id INTEGER NOT NULL REFERENCES novel_metadata(id) ON DELETE CASCADE,
    small_story_index INTEGER NOT NULL,
    phase_start_ch INTEGER NOT NULL,
    phase_end_ch INTEGER NOT NULL,
    plan_macro TEXT NOT NULL DEFAULT '',
    plan_phase TEXT NOT NULL DEFAULT '',
    plan_macro_version INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =============================================
-- 索引
-- =============================================
CREATE INDEX IF NOT EXISTS idx_character_novel ON character(novel_id);
CREATE INDEX IF NOT EXISTS idx_character_name ON character(name);
CREATE INDEX IF NOT EXISTS idx_power_change_character ON power_change_log(character_id);
CREATE INDEX IF NOT EXISTS idx_power_change_chapter ON power_change_log(chapter_no);
CREATE INDEX IF NOT EXISTS idx_item_owner ON item(owner_id);
CREATE INDEX IF NOT EXISTS idx_item_novel ON item(novel_id);
CREATE INDEX IF NOT EXISTS idx_item_log_item ON item_log(item_id);
CREATE INDEX IF NOT EXISTS idx_item_log_character ON item_log(character_id);
CREATE INDEX IF NOT EXISTS idx_plot_thread_novel ON plot_thread(novel_id);
CREATE INDEX IF NOT EXISTS idx_plot_thread_status ON plot_thread(status);
CREATE INDEX IF NOT EXISTS idx_chapter_novel ON chapter(novel_id);
CREATE INDEX IF NOT EXISTS idx_chapter_volume ON chapter(volume_id);
CREATE INDEX IF NOT EXISTS idx_chapter_order ON chapter(chapter_order);
CREATE INDEX IF NOT EXISTS idx_memory_volume_vol ON memory_volume(volume_id);
CREATE INDEX IF NOT EXISTS idx_memory_chapter_ch ON memory_chapter(chapter_id);
CREATE INDEX IF NOT EXISTS idx_trope_novel ON trope_template(novel_id);
CREATE INDEX IF NOT EXISTS idx_small_story_novel ON small_story_tracking(novel_id);
