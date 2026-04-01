export interface User {
  google_id: string;
  email: string;
  name: string;
  is_admin?: boolean;
  credit_balance?: number;
  credits_used?: number;
}

export interface DriveFolder {
  id: string;
  name: string;
  mimeType: string;
  modifiedTime?: string;
}

export interface DriveFile {
  id: string;
  name: string;
  mimeType: string;
  size?: string;
  modifiedTime?: string;
}

export interface Product {
  id: string;
  [key: string]: unknown;
}

export type JobStatus =
  | "queued"
  | "strategy"
  | "batch_submitted"
  | "generating"
  | "completed"
  | "failed";

export type JobType = "full_listing" | "image_only";

export type ImageCategory = "white_bg" | "scene" | "model" | "detail";

export type AspectRatio = "1:1" | "3:4" | "4:3";

export type ImageModel = "gemini-3-pro-image-preview" | "gemini-3.1-flash-image-preview";

export type ImageResolution = "1k" | "2k";

export interface ImageConfig {
  category: ImageCategory | null;
  additional_prompt: string;
  count: number;
  aspect_ratio: AspectRatio;
  model: ImageModel;
  resolution: ImageResolution;
}

export interface Job {
  id?: number;
  job_id: string;
  product_id: string;
  category: string;
  job_type?: JobType;
  status: JobStatus;
  progress: number;
  stage_name: string;
  image_urls: string[] | null;
  result: Record<string, unknown> | null;
  prompts?: Record<string, string>;
  error_message: string | null;
  cost_usd: number;
  created_at: string;
  updated_at: string;
}

export interface JobListResponse {
  jobs: Job[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface ApiKey {
  id: number;
  name: string;
  rate_limit_rpm: number;
  revoked: boolean;
  created_at: string;
  last_used_at: string | null;
}

export interface ApiKeyCreated {
  id: number;
  name: string;
  raw_key: string;
  rate_limit_rpm: number;
  created_at: string;
}

export interface ApiKeyListResponse {
  keys: ApiKey[];
}

/** Legacy — kept for backwards compat with existing components */
export interface GenerateJob {
  id: number;
  product_id: string;
  category: string;
  status: "pending" | "running" | "completed" | "failed";
  cost_usd: number;
  created_at: string;
}

export interface ImageResult {
  direction: string;
  url: string;
  index: number;
}

export interface ImageStrategySlot {
  slot: number;
  type: string;
  category: "required" | "strategic";
  description: string;
  rationale: string;
}

export interface ImageStrategy {
  $schema: string;
  product_id: string;
  analysis: {
    product_usps: string[];
    target_customer: string;
    purchase_barriers: string[];
    competitive_gap: string;
  };
  slots: ImageStrategySlot[];
}

export interface GenerateResults {
  listing?: EtsyListing;
  prompts?: PromptBundle;
  product_data?: Record<string, unknown>;
  strategy?: ImageStrategy;
}

export interface EtsyListing {
  title: string;
  title_variations?: string[];
  tags: string;
  long_tail_keywords?: string[];
  description: string;
  attributes?: Record<string, unknown>;
  [key: string]: unknown;
}

export interface PromptBundle {
  product_id?: string;
  category?: string;
  style?: string;
  materials?: string[];
  prompts: PromptCard[];
}

export interface PromptCard {
  index: number;
  type: string;
  type_name?: string;
  goal?: string;
  reference_images?: string[];
  prompt: string;
}

export type SSEEvent =
  | { event: "start"; data: { product_id: string; status: string } }
  | { event: "progress"; data: { stage: string; node?: string; message: string } }
  | { event: "strategy_complete"; data: { strategy: ImageStrategy } }
  | { event: "image_complete"; data: ImageResult }
  | { event: "image_done"; data: { total: number; failed: number } }
  | {
      event: "complete";
      data: {
        product_id: string;
        status: string;
        results?: GenerateResults;
        run_id?: string;
      };
    }
  | { event: "error"; data: { message: string } };
