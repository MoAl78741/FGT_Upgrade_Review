export type JobStatus = "pending" | "running" | "completed" | "failed";

export interface Job {
  id: string;
  from_version: string;
  to_version: string;
  status: JobStatus;
  use_selenium: boolean;
  source?: "scrape" | "pdf";
  created_at: string;
  completed_at?: string;
  error_message?: string;
  log?: string;
}

export interface TableItem {
  "Bug ID": string;
  Description: string;
}

export interface Feature {
  category: string;
  "Feature ID": string;
  Description: string;
}

export interface KnownIssue {
  category: string;
  "Bug ID": string;
  Description: string;
}

export interface Notice {
  title: string;
  content: string;
  markdown?: string;
}

export interface RichBlock {
  type: "heading" | "paragraph" | "list" | "table" | "code";
  level?: number;
  text?: string;
  bold?: boolean;
  items?: string[];
  headers?: string[];
  rows?: string[][];
}

export interface RichSection {
  title: string;
  blocks: RichBlock[];
  markdown?: string;
}

export interface VersionData {
  changes_cli?: TableItem[];
  changes_default?: TableItem[];
  changes_tablesize?: TableItem[];
  new_features?: Feature[];
  known_issues?: KnownIssue[];
  _section_urls?: Record<string, string>;
  // Extended sections from full-document scraper (slug keys)
  [slug: string]: TableItem[] | Feature[] | KnownIssue[] | RichSection | Record<string, string> | undefined;
}

export interface JobDetail extends Job {
  versions?: string[];
  all_data?: Record<string, VersionData>;
  special_notices?: Notice[];
}
