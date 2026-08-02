export type Json =
  | string
  | number
  | boolean
  | null
  | { [key: string]: Json | undefined }
  | Json[]

export type Database = {
  graphql_public: {
    Tables: {
      [_ in never]: never
    }
    Views: {
      [_ in never]: never
    }
    Functions: {
      graphql: {
        Args: {
          extensions?: Json
          operationName?: string
          query?: string
          variables?: Json
        }
        Returns: Json
      }
    }
    Enums: {
      [_ in never]: never
    }
    CompositeTypes: {
      [_ in never]: never
    }
  }
  public: {
    Tables: {
      ai_usage_events: {
        Row: {
          created_at: string
          error_code: string | null
          id: string
          input_tokens: number | null
          is_pro: boolean
          model: string
          output_tokens: number | null
          provider: string
          route: string
          status: string
          total_tokens: number | null
          used_server_key: boolean
          user_id: string
        }
        Insert: {
          created_at?: string
          error_code?: string | null
          id?: string
          input_tokens?: number | null
          is_pro?: boolean
          model: string
          output_tokens?: number | null
          provider: string
          route: string
          status: string
          total_tokens?: number | null
          used_server_key?: boolean
          user_id: string
        }
        Update: {
          created_at?: string
          error_code?: string | null
          id?: string
          input_tokens?: number | null
          is_pro?: boolean
          model?: string
          output_tokens?: number | null
          provider?: string
          route?: string
          status?: string
          total_tokens?: number | null
          used_server_key?: boolean
          user_id?: string
        }
        Relationships: []
      }
      jobs: {
        Row: {
          company_name: string | null
          created_at: string
          description: string | null
          employment_type: string | null
          id: string
          is_active: boolean | null
          job_url: string | null
          keywords: Json | null
          location: string | null
          position_title: string
          salary_range: string | null
          updated_at: string
          user_id: string
          work_location: string | null
        }
        Insert: {
          company_name?: string | null
          created_at?: string
          description?: string | null
          employment_type?: string | null
          id?: string
          is_active?: boolean | null
          job_url?: string | null
          keywords?: Json | null
          location?: string | null
          position_title: string
          salary_range?: string | null
          updated_at?: string
          user_id: string
          work_location?: string | null
        }
        Update: {
          company_name?: string | null
          created_at?: string
          description?: string | null
          employment_type?: string | null
          id?: string
          is_active?: boolean | null
          job_url?: string | null
          keywords?: Json | null
          location?: string | null
          position_title?: string
          salary_range?: string | null
          updated_at?: string
          user_id?: string
          work_location?: string | null
        }
        Relationships: []
      }
      profiles: {
        Row: {
          certifications: Json | null
          created_at: string
          education: Json | null
          email: string | null
          first_name: string | null
          github_url: string | null
          is_admin: boolean
          last_name: string | null
          linkedin_url: string | null
          location: string | null
          phone_number: string | null
          projects: Json | null
          skills: Json | null
          updated_at: string
          user_id: string
          website: string | null
          work_experience: Json | null
        }
        Insert: {
          certifications?: Json | null
          created_at?: string
          education?: Json | null
          email?: string | null
          first_name?: string | null
          github_url?: string | null
          is_admin?: boolean
          last_name?: string | null
          linkedin_url?: string | null
          location?: string | null
          phone_number?: string | null
          projects?: Json | null
          skills?: Json | null
          updated_at?: string
          user_id: string
          website?: string | null
          work_experience?: Json | null
        }
        Update: {
          certifications?: Json | null
          created_at?: string
          education?: Json | null
          email?: string | null
          first_name?: string | null
          github_url?: string | null
          is_admin?: boolean
          last_name?: string | null
          linkedin_url?: string | null
          location?: string | null
          phone_number?: string | null
          projects?: Json | null
          skills?: Json | null
          updated_at?: string
          user_id?: string
          website?: string | null
          work_experience?: Json | null
        }
        Relationships: []
      }
      resumes: {
        Row: {
          certifications: Json | null
          cover_letter: Json | null
          created_at: string
          document_settings: Json | null
          education: Json | null
          email: string | null
          first_name: string | null
          github_url: string | null
          has_cover_letter: boolean
          id: string
          is_base_resume: boolean | null
          job_id: string | null
          last_name: string | null
          linkedin_url: string | null
          location: string | null
          name: string
          phone_number: string | null
          professional_summary: string | null
          projects: Json | null
          resume_title: string | null
          section_configs: Json | null
          section_order: Json | null
          skills: Json | null
          target_role: string | null
          updated_at: string
          user_id: string
          website: string | null
          work_experience: Json | null
        }
        Insert: {
          certifications?: Json | null
          cover_letter?: Json | null
          created_at?: string
          document_settings?: Json | null
          education?: Json | null
          email?: string | null
          first_name?: string | null
          github_url?: string | null
          has_cover_letter?: boolean
          id?: string
          is_base_resume?: boolean | null
          job_id?: string | null
          last_name?: string | null
          linkedin_url?: string | null
          location?: string | null
          name: string
          phone_number?: string | null
          professional_summary?: string | null
          projects?: Json | null
          resume_title?: string | null
          section_configs?: Json | null
          section_order?: Json | null
          skills?: Json | null
          target_role?: string | null
          updated_at?: string
          user_id: string
          website?: string | null
          work_experience?: Json | null
        }
        Update: {
          certifications?: Json | null
          cover_letter?: Json | null
          created_at?: string
          document_settings?: Json | null
          education?: Json | null
          email?: string | null
          first_name?: string | null
          github_url?: string | null
          has_cover_letter?: boolean
          id?: string
          is_base_resume?: boolean | null
          job_id?: string | null
          last_name?: string | null
          linkedin_url?: string | null
          location?: string | null
          name?: string
          phone_number?: string | null
          professional_summary?: string | null
          projects?: Json | null
          resume_title?: string | null
          section_configs?: Json | null
          section_order?: Json | null
          skills?: Json | null
          target_role?: string | null
          updated_at?: string
          user_id?: string
          website?: string | null
          work_experience?: Json | null
        }
        Relationships: [
          {
            foreignKeyName: "resumes_job_id_fkey"
            columns: ["job_id"]
            isOneToOne: false
            referencedRelation: "jobs"
            referencedColumns: ["id"]
          },
        ]
      }
      rs_activity_logs: {
        Row: {
          action: string
          created_at: string
          entity_id: string | null
          entity_type: string
          id: string
          metadata: Json
          user_id: string
        }
        Insert: {
          action: string
          created_at?: string
          entity_id?: string | null
          entity_type?: string
          id?: string
          metadata?: Json
          user_id: string
        }
        Update: {
          action?: string
          created_at?: string
          entity_id?: string | null
          entity_type?: string
          id?: string
          metadata?: Json
          user_id?: string
        }
        Relationships: []
      }
      rs_agent_runs: {
        Row: {
          agent_key: string
          created_at: string
          documents: number | null
          finished_at: string | null
          id: string
          latency_ms: number | null
          model: string | null
          output: Json | null
          session_id: string
          sources: number | null
          started_at: string | null
          status: string
          tokens: number | null
        }
        Insert: {
          agent_key: string
          created_at?: string
          documents?: number | null
          finished_at?: string | null
          id?: string
          latency_ms?: number | null
          model?: string | null
          output?: Json | null
          session_id: string
          sources?: number | null
          started_at?: string | null
          status?: string
          tokens?: number | null
        }
        Update: {
          agent_key?: string
          created_at?: string
          documents?: number | null
          finished_at?: string | null
          id?: string
          latency_ms?: number | null
          model?: string | null
          output?: Json | null
          session_id?: string
          sources?: number | null
          started_at?: string | null
          status?: string
          tokens?: number | null
        }
        Relationships: [
          {
            foreignKeyName: "rs_agent_runs_session_id_fkey"
            columns: ["session_id"]
            isOneToOne: false
            referencedRelation: "rs_research_sessions"
            referencedColumns: ["id"]
          },
        ]
      }
      rs_collection_items: {
        Row: {
          collection_id: string
          created_at: string
          document_id: string
          report_id: string
        }
        Insert: {
          collection_id: string
          created_at?: string
          document_id: string
          report_id: string
        }
        Update: {
          collection_id?: string
          created_at?: string
          document_id?: string
          report_id?: string
        }
        Relationships: [
          {
            foreignKeyName: "rs_collection_items_collection_id_fkey"
            columns: ["collection_id"]
            isOneToOne: false
            referencedRelation: "rs_collections"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "rs_collection_items_document_id_fkey"
            columns: ["document_id"]
            isOneToOne: false
            referencedRelation: "rs_documents"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "rs_collection_items_report_id_fkey"
            columns: ["report_id"]
            isOneToOne: false
            referencedRelation: "rs_reports"
            referencedColumns: ["id"]
          },
        ]
      }
      rs_collections: {
        Row: {
          created_at: string
          description: string
          id: string
          name: string
          updated_at: string
          user_id: string
        }
        Insert: {
          created_at?: string
          description?: string
          id?: string
          name: string
          updated_at?: string
          user_id: string
        }
        Update: {
          created_at?: string
          description?: string
          id?: string
          name?: string
          updated_at?: string
          user_id?: string
        }
        Relationships: []
      }
      rs_documents: {
        Row: {
          chunks: number | null
          created_at: string
          error: string | null
          id: string
          mime_type: string
          name: string
          pages: number | null
          size_bytes: number
          status: string
          storage_path: string
          updated_at: string
          user_id: string
        }
        Insert: {
          chunks?: number | null
          created_at?: string
          error?: string | null
          id?: string
          mime_type?: string
          name: string
          pages?: number | null
          size_bytes?: number
          status?: string
          storage_path: string
          updated_at?: string
          user_id: string
        }
        Update: {
          chunks?: number | null
          created_at?: string
          error?: string | null
          id?: string
          mime_type?: string
          name?: string
          pages?: number | null
          size_bytes?: number
          status?: string
          storage_path?: string
          updated_at?: string
          user_id?: string
        }
        Relationships: []
      }
      rs_messages: {
        Row: {
          content: string
          created_at: string
          id: string
          metadata: Json
          role: string
          session_id: string
        }
        Insert: {
          content?: string
          created_at?: string
          id?: string
          metadata?: Json
          role: string
          session_id: string
        }
        Update: {
          content?: string
          created_at?: string
          id?: string
          metadata?: Json
          role?: string
          session_id?: string
        }
        Relationships: [
          {
            foreignKeyName: "rs_messages_session_id_fkey"
            columns: ["session_id"]
            isOneToOne: false
            referencedRelation: "rs_research_sessions"
            referencedColumns: ["id"]
          },
        ]
      }
      rs_profiles: {
        Row: {
          avatar_url: string | null
          created_at: string
          email: string
          id: string
          is_active: boolean
          legacy_user_id: string | null
          name: string
          updated_at: string
        }
        Insert: {
          avatar_url?: string | null
          created_at?: string
          email: string
          id: string
          is_active?: boolean
          legacy_user_id?: string | null
          name?: string
          updated_at?: string
        }
        Update: {
          avatar_url?: string | null
          created_at?: string
          email?: string
          id?: string
          is_active?: boolean
          legacy_user_id?: string | null
          name?: string
          updated_at?: string
        }
        Relationships: []
      }
      rs_recent_searches: {
        Row: {
          created_at: string
          id: string
          query: string
          user_id: string
        }
        Insert: {
          created_at?: string
          id?: string
          query: string
          user_id: string
        }
        Update: {
          created_at?: string
          id?: string
          query?: string
          user_id?: string
        }
        Relationships: []
      }
      rs_reports: {
        Row: {
          content_md: string
          created_at: string
          format: string
          id: string
          is_favorite: boolean
          is_pinned: boolean
          metrics: Json
          session_id: string | null
          sources: Json
          status: string
          storage_path: string | null
          title: string
          updated_at: string
          user_id: string
        }
        Insert: {
          content_md?: string
          created_at?: string
          format?: string
          id?: string
          is_favorite?: boolean
          is_pinned?: boolean
          metrics?: Json
          session_id?: string | null
          sources?: Json
          status?: string
          storage_path?: string | null
          title: string
          updated_at?: string
          user_id: string
        }
        Update: {
          content_md?: string
          created_at?: string
          format?: string
          id?: string
          is_favorite?: boolean
          is_pinned?: boolean
          metrics?: Json
          session_id?: string | null
          sources?: Json
          status?: string
          storage_path?: string | null
          title?: string
          updated_at?: string
          user_id?: string
        }
        Relationships: [
          {
            foreignKeyName: "rs_reports_session_id_fkey"
            columns: ["session_id"]
            isOneToOne: false
            referencedRelation: "rs_research_sessions"
            referencedColumns: ["id"]
          },
        ]
      }
      rs_research_sessions: {
        Row: {
          created_at: string
          debate_enabled: boolean
          error: string | null
          id: string
          mode: string
          prompt: string
          sources_total: number
          status: string
          title: string
          updated_at: string
          user_id: string
        }
        Insert: {
          created_at?: string
          debate_enabled?: boolean
          error?: string | null
          id?: string
          mode?: string
          prompt: string
          sources_total?: number
          status?: string
          title?: string
          updated_at?: string
          user_id: string
        }
        Update: {
          created_at?: string
          debate_enabled?: boolean
          error?: string | null
          id?: string
          mode?: string
          prompt?: string
          sources_total?: number
          status?: string
          title?: string
          updated_at?: string
          user_id?: string
        }
        Relationships: []
      }
      rs_run_metrics: {
        Row: {
          chunks: number
          completion_tokens: number
          created_at: string
          documents: number
          estimated_cost: number
          execution_time_ms: number | null
          id: string
          prompt_tokens: number
          relevant_sources: number
          session_id: string
          sources_found: number
          total_tokens: number
        }
        Insert: {
          chunks?: number
          completion_tokens?: number
          created_at?: string
          documents?: number
          estimated_cost?: number
          execution_time_ms?: number | null
          id?: string
          prompt_tokens?: number
          relevant_sources?: number
          session_id: string
          sources_found?: number
          total_tokens?: number
        }
        Update: {
          chunks?: number
          completion_tokens?: number
          created_at?: string
          documents?: number
          estimated_cost?: number
          execution_time_ms?: number | null
          id?: string
          prompt_tokens?: number
          relevant_sources?: number
          session_id?: string
          sources_found?: number
          total_tokens?: number
        }
        Relationships: [
          {
            foreignKeyName: "rs_run_metrics_session_id_fkey"
            columns: ["session_id"]
            isOneToOne: false
            referencedRelation: "rs_research_sessions"
            referencedColumns: ["id"]
          },
        ]
      }
      rs_saved_prompts: {
        Row: {
          created_at: string
          id: string
          label: string
          prompt: string
          updated_at: string
          usage_count: number
          user_id: string
        }
        Insert: {
          created_at?: string
          id?: string
          label: string
          prompt: string
          updated_at?: string
          usage_count?: number
          user_id: string
        }
        Update: {
          created_at?: string
          id?: string
          label?: string
          prompt?: string
          updated_at?: string
          usage_count?: number
          user_id?: string
        }
        Relationships: []
      }
      rs_settings: {
        Row: {
          preferences: Json
          updated_at: string
          user_id: string
        }
        Insert: {
          preferences?: Json
          updated_at?: string
          user_id: string
        }
        Update: {
          preferences?: Json
          updated_at?: string
          user_id?: string
        }
        Relationships: []
      }
      stripe_webhook_events: {
        Row: {
          created_at: string
          event_id: string
          event_type: string
          processed_at: string | null
          updated_at: string
        }
        Insert: {
          created_at?: string
          event_id: string
          event_type: string
          processed_at?: string | null
          updated_at?: string
        }
        Update: {
          created_at?: string
          event_id?: string
          event_type?: string
          processed_at?: string | null
          updated_at?: string
        }
        Relationships: []
      }
      subscriptions: {
        Row: {
          created_at: string
          current_period_end: string | null
          stripe_customer_id: string | null
          stripe_subscription_id: string | null
          subscription_plan: string | null
          subscription_status: string | null
          trial_end: string | null
          updated_at: string
          user_id: string
        }
        Insert: {
          created_at?: string
          current_period_end?: string | null
          stripe_customer_id?: string | null
          stripe_subscription_id?: string | null
          subscription_plan?: string | null
          subscription_status?: string | null
          trial_end?: string | null
          updated_at?: string
          user_id: string
        }
        Update: {
          created_at?: string
          current_period_end?: string | null
          stripe_customer_id?: string | null
          stripe_subscription_id?: string | null
          subscription_plan?: string | null
          subscription_status?: string | null
          trial_end?: string | null
          updated_at?: string
          user_id?: string
        }
        Relationships: []
      }
    }
    Views: {
      [_ in never]: never
    }
    Functions: {
      [_ in never]: never
    }
    Enums: {
      [_ in never]: never
    }
    CompositeTypes: {
      [_ in never]: never
    }
  }
}

type DatabaseWithoutInternals = Omit<Database, "__InternalSupabase">

type DefaultSchema = DatabaseWithoutInternals[Extract<keyof Database, "public">]

export type Tables<
  DefaultSchemaTableNameOrOptions extends
    | keyof (DefaultSchema["Tables"] & DefaultSchema["Views"])
    | { schema: keyof DatabaseWithoutInternals },
  TableName extends DefaultSchemaTableNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof (DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"] &
        DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Views"])
    : never = never,
> = DefaultSchemaTableNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? (DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"] &
      DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Views"])[TableName] extends {
      Row: infer R
    }
    ? R
    : never
  : DefaultSchemaTableNameOrOptions extends keyof (DefaultSchema["Tables"] &
        DefaultSchema["Views"])
    ? (DefaultSchema["Tables"] &
        DefaultSchema["Views"])[DefaultSchemaTableNameOrOptions] extends {
        Row: infer R
      }
      ? R
      : never
    : never

export type TablesInsert<
  DefaultSchemaTableNameOrOptions extends
    | keyof DefaultSchema["Tables"]
    | { schema: keyof DatabaseWithoutInternals },
  TableName extends DefaultSchemaTableNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"]
    : never = never,
> = DefaultSchemaTableNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"][TableName] extends {
      Insert: infer I
    }
    ? I
    : never
  : DefaultSchemaTableNameOrOptions extends keyof DefaultSchema["Tables"]
    ? DefaultSchema["Tables"][DefaultSchemaTableNameOrOptions] extends {
        Insert: infer I
      }
      ? I
      : never
    : never

export type TablesUpdate<
  DefaultSchemaTableNameOrOptions extends
    | keyof DefaultSchema["Tables"]
    | { schema: keyof DatabaseWithoutInternals },
  TableName extends DefaultSchemaTableNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"]
    : never = never,
> = DefaultSchemaTableNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"][TableName] extends {
      Update: infer U
    }
    ? U
    : never
  : DefaultSchemaTableNameOrOptions extends keyof DefaultSchema["Tables"]
    ? DefaultSchema["Tables"][DefaultSchemaTableNameOrOptions] extends {
        Update: infer U
      }
      ? U
      : never
    : never

export type Enums<
  DefaultSchemaEnumNameOrOptions extends
    | keyof DefaultSchema["Enums"]
    | { schema: keyof DatabaseWithoutInternals },
  EnumName extends DefaultSchemaEnumNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[DefaultSchemaEnumNameOrOptions["schema"]]["Enums"]
    : never = never,
> = DefaultSchemaEnumNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[DefaultSchemaEnumNameOrOptions["schema"]]["Enums"][EnumName]
  : DefaultSchemaEnumNameOrOptions extends keyof DefaultSchema["Enums"]
    ? DefaultSchema["Enums"][DefaultSchemaEnumNameOrOptions]
    : never

export type CompositeTypes<
  PublicCompositeTypeNameOrOptions extends
    | keyof DefaultSchema["CompositeTypes"]
    | { schema: keyof DatabaseWithoutInternals },
  CompositeTypeName extends PublicCompositeTypeNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[PublicCompositeTypeNameOrOptions["schema"]]["CompositeTypes"]
    : never = never,
> = PublicCompositeTypeNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[PublicCompositeTypeNameOrOptions["schema"]]["CompositeTypes"][CompositeTypeName]
  : PublicCompositeTypeNameOrOptions extends keyof DefaultSchema["CompositeTypes"]
    ? DefaultSchema["CompositeTypes"][PublicCompositeTypeNameOrOptions]
    : never

export const Constants = {
  graphql_public: {
    Enums: {},
  },
  public: {
    Enums: {},
  },
} as const

