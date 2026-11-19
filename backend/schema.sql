-- CiteVerify Supabase Database Schema

-- Documents table
CREATE TABLE IF NOT EXISTS documents (
    id TEXT PRIMARY KEY,
    filename TEXT NOT NULL,
    extracted_text TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'uploaded',
    error_message TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- Claims table
CREATE TABLE IF NOT EXISTS claims (
    id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    claim_text TEXT NOT NULL,
    in_text_citation TEXT NOT NULL,
    reference_string TEXT NOT NULL,
    search_query TEXT NOT NULL,
    verdict TEXT NOT NULL,
    confidence FLOAT NOT NULL,
    explanation TEXT NOT NULL,
    evidence_passage TEXT DEFAULT '',
    source_title TEXT,
    source_authors JSONB,
    source_year INTEGER,
    source_doi TEXT,
    source_url TEXT,
    source_abstract TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- Indices for fast lookups
CREATE INDEX IF NOT EXISTS idx_documents_created_at ON documents(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_claims_document_id ON claims(document_id);
