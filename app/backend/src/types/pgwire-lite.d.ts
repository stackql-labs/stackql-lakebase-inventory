declare module '@stackql/pgwire-lite' {
  interface PgwireOptions {
    user: string;
    database: string;
    host: string;
    port: number;
    debug?: boolean;
    cert?: string;
    key?: string;
    ca?: string;
    useTLS: boolean;
  }

  interface PgwireResult {
    data: Record<string, unknown>[];
  }

  export function runQuery(options: PgwireOptions, query: string): Promise<PgwireResult>;
}
