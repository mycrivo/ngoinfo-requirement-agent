# Database Migrations with Alembic

This project uses Alembic for database schema management. Migrations are automatically run on application startup to ensure the database schema is always up to date.

## Overview

- **Baseline Migration**: `0001_baseline.py` - Creates the initial database schema
- **Variants Migration**: `0002_add_variants.py` - Adds JSONB variants column
- **Target Schema Migration**: `0003_add_target_schema_tables.py` - Adds proposal_templates, documents, sources, ingestion_runs
- **Auto-migration**: Migrations run automatically when the app starts
- **Fallback**: Local development can use `DEV_CREATE_TABLES=true` for direct table creation

## Quick Commands

```bash
# View available commands
make help

# Create new migration
make alembic-new msg="description of changes"

# Upgrade to latest
make alembic-up

# Downgrade one step
make alembic-down

# Check status
make alembic-status

# View history
make alembic-history

# Run data backfill
make backfill
```

## Creating a New Migration

### 1. Generate Migration File

```bash
# Create a new migration with auto-detection of schema changes
make alembic-new msg="description of changes"

# Or manually
alembic revision --autogenerate -m "description of changes"

# Create an empty migration file
alembic revision -m "description of changes"
```

### 2. Review and Edit Migration

The generated migration file will be in `migrations/versions/`. Review the generated SQL and modify if needed:

```python
def upgrade() -> None:
    # Add your schema changes here
    op.add_column('table_name', sa.Column('new_column', sa.String()))

def downgrade() -> None:
    # Add rollback logic here
    op.drop_column('table_name', 'new_column')
```

### 3. Test Migration

```bash
# Test upgrade
make alembic-up

# Test downgrade (if needed)
make alembic-down
```

## Running Migrations

### Automatic (Production)

Migrations run automatically when the application starts. If migrations fail, the application will start in degraded mode and expose `/admin/migrations` for retry.

### Manual

```bash
# Check current status
make alembic-status

# Check migration history
make alembic-history

# Upgrade to latest
make alembic-up

# Upgrade to specific revision
alembic upgrade 0003

# Downgrade
make alembic-down

# Downgrade to specific revision
alembic downgrade 0001
```

### Using Migration Utility

```bash
# Run migrations programmatically
python utils/migrate.py

# Check migration status
python utils/migrate.py status
```

## Development vs Production

### Development

Set `DEV_CREATE_TABLES=true` in your `.env` file to enable fallback table creation:

```bash
DEV_CREATE_TABLES=true
```

This allows the app to start even if migrations fail, useful for local development.

### Production

In production (Railway), migrations run automatically on startup. The fallback table creation is disabled to ensure schema consistency.

## 🚨 **OPERATIONAL RUNBOOK**

### **Emergency Migration Procedures**

#### **Migration Failure on Startup**

**Symptoms:**
- Application starts but health check shows `"migrations": "failed"`
- Database operations may fail
- `/health` endpoint returns `"status": "degraded"`

**Immediate Actions:**
1. **Check application logs** for migration error details
2. **Access migration dashboard** at `/admin/migrations`
3. **Review migration status** - current vs target revision
4. **Attempt retry** using the "Retry Migrations" button

**If Retry Fails:**
1. **Check database connectivity** - ensure PostgreSQL is accessible
2. **Verify migration files** - ensure all migration files are present
3. **Check disk space** - ensure sufficient storage for database operations
4. **Review database permissions** - ensure user has CREATE/ALTER privileges

#### **Rollback Procedures**

**When to Rollback:**
- Migration causes data corruption
- Application functionality breaks
- Performance degradation

**Rollback Commands:**
```bash
# Rollback one migration
make alembic-down

# Rollback to specific revision
alembic downgrade 0002

# Rollback to baseline (⚠️ DESTRUCTIVE)
alembic downgrade base
```

**Post-Rollback Actions:**
1. **Verify application functionality** - test core features
2. **Check data integrity** - ensure no data loss
3. **Investigate root cause** - fix migration issues
4. **Test migration locally** before redeploying

### **Railway Deployment Workflow**

#### **Pre-Deployment Checklist**

- [ ] **Database backup** completed (if production)
- [ ] **Migration files** committed and pushed
- [ ] **Local testing** completed successfully
- [ ] **Rollback plan** prepared
- [ ] **Team notification** sent

#### **Deployment Sequence**

1. **Deploy migration files** first
2. **Monitor migration execution** via logs
3. **Verify schema changes** via health check
4. **Deploy application code**
5. **Run post-deployment backfill** if needed

#### **Post-Deployment Verification**

```bash
# Check application health
curl https://your-app.railway.app/health

# Verify migration status
curl https://your-app.railway.app/admin/migrations

# Run backfill if needed
make backfill
```

### **Common Migration Failures & Solutions**

#### **1. Connection Timeout**

**Error:** `psycopg2.OperationalError: connection to server at... failed: Connection timed out`

**Solutions:**
- Check database server status
- Verify network connectivity
- Increase connection timeout in `alembic.ini`
- Check firewall rules

#### **2. Permission Denied**

**Error:** `psycopg2.ProgrammingError: permission denied for...`

**Solutions:**
- Verify database user permissions
- Check role assignments
- Ensure user has CREATE/ALTER privileges
- Review database security policies

#### **3. Disk Space Issues**

**Error:** `psycopg2.OperationalError: could not write to file...`

**Solutions:**
- Check available disk space
- Clean up temporary files
- Monitor disk usage trends
- Scale storage if needed

#### **4. Lock Conflicts**

**Error:** `psycopg2.OperationalError: could not obtain lock on relation...`

**Solutions:**
- Check for long-running transactions
- Kill blocking processes if safe
- Schedule migration during low-traffic period
- Use `NOWAIT` option for non-blocking operations

### **Data Backfill Procedures**

#### **When to Run Backfill**

- After major schema changes
- When adding new required fields
- To normalize legacy data
- To seed default data

#### **Backfill Commands**

```bash
# Full backfill (all operations)
make backfill

# Specific operations
make backfill-hashes      # Proposal template hashes
make backfill-variants    # Normalize variants data
make backfill-sources     # Seed default sources
make backfill-cleanup     # Clean orphaned records

# Dry run (preview changes)
make backfill-dry-run
```

#### **Backfill Safety Checks**

- **Always test locally** first
- **Use dry-run mode** to preview changes
- **Backup database** before major backfills
- **Monitor progress** via logs
- **Verify results** after completion

### **Monitoring & Alerting**

#### **Health Check Endpoints**

```bash
# Application health
GET /health

# Migration status
GET /admin/migrations

# Database connectivity
GET /health (check database field)
```

#### **Log Monitoring**

**Key Log Patterns:**
```
✅ Database migrations completed successfully
❌ Database migrations failed
🔄 Running database migrations...
🚨 Application will start but database operations may fail
```

#### **Alert Thresholds**

- **Migration failure** - Immediate alert
- **Schema out of sync** - Warning alert
- **Backfill failures** - Error alert
- **Database connectivity issues** - Critical alert

### **Recovery Procedures**

#### **Complete Database Failure**

1. **Stop application** to prevent further damage
2. **Assess data loss** - determine recovery point
3. **Restore from backup** if available
4. **Run migrations** to current schema
5. **Verify data integrity** before restarting
6. **Gradually restore services** monitoring health

#### **Partial Schema Corruption**

1. **Identify affected tables/columns**
2. **Isolate corrupted data** if possible
3. **Run targeted migrations** to fix schema
4. **Validate data consistency**
5. **Run backfill** to restore missing data
6. **Monitor for additional issues**

### **Performance Considerations**

#### **Migration Optimization**

- **Batch operations** for large datasets
- **Index management** during migrations
- **Transaction size** limits
- **Parallel processing** where safe

#### **Downtime Minimization**

- **Zero-downtime migrations** where possible
- **Blue-green deployment** for major changes
- **Rolling updates** for non-breaking changes
- **Feature flags** for gradual rollouts

### **Documentation & Training**

#### **Team Knowledge Requirements**

- **Migration procedures** - all developers
- **Rollback procedures** - senior developers
- **Emergency contacts** - operations team
- **Recovery procedures** - database administrators

#### **Regular Reviews**

- **Migration success rates** - monthly
- **Rollback frequency** - quarterly
- **Performance impact** - post-migration
- **Process improvements** - continuous

---

## **Emergency Contacts**

- **Database Administrator:** [Contact Info]
- **Lead Developer:** [Contact Info]
- **Operations Team:** [Contact Info]
- **On-Call Engineer:** [Contact Info]

## **Useful Resources**

- [Alembic Documentation](https://alembic.sqlalchemy.org/)
- [PostgreSQL Migration Best Practices](https://www.postgresql.org/docs/current/ddl.html)
- [Railway Deployment Guide](https://docs.railway.app/)
- [FastAPI Health Checks](https://fastapi.tiangolo.com/tutorial/health-check/)
