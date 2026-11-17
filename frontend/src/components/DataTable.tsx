import {
  flexRender, getCoreRowModel, getPaginationRowModel, getSortedRowModel, useReactTable,
  type ColumnDef, type SortingState,
} from '@tanstack/react-table'
import { ArrowDown, ArrowUp, ArrowUpDown, ChevronLeft, ChevronRight } from 'lucide-react'
import { useState } from 'react'
import { Button } from '@/components/ui/primitives'
import { cn } from '@/lib/utils'

export function DataTable<T>({ data, columns, pageSize = 25, onRowClick, initialSort, dense, testId }: {
  data: T[]; columns: ColumnDef<T, unknown>[]; pageSize?: number; onRowClick?: (row: T) => void
  initialSort?: SortingState; dense?: boolean; testId?: string
}) {
  const [sorting, setSorting] = useState<SortingState>(initialSort ?? [])
  const table = useReactTable({
    data, columns, state: { sorting }, onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(), getSortedRowModel: getSortedRowModel(), getPaginationRowModel: getPaginationRowModel(),
    initialState: { pagination: { pageSize } },
  })
  const pages = table.getPageCount()
  return (
    <div>
      <div className="overflow-x-auto scroll-thin">
        <table data-testid={testId} className="w-full min-w-[720px] border-separate border-spacing-0 text-left text-[13px]">
          <thead>
            {table.getHeaderGroups().map((hg) => (
              <tr key={hg.id}>
                {hg.headers.map((h) => {
                  const sorted = h.column.getIsSorted()
                  const can = h.column.getCanSort()
                  return (
                    <th key={h.id} className="sticky top-0 border-b border-line bg-panel/90 px-3 py-2.5 text-[10.5px] font-semibold uppercase tracking-wider text-faint backdrop-blur first:pl-5 last:pr-5">
                      {h.isPlaceholder ? null : (
                        <button disabled={!can} onClick={h.column.getToggleSortingHandler()}
                          className={cn('inline-flex items-center gap-1', can && 'hover:text-ink', (h.column.columnDef.meta as { align?: string })?.align === 'right' && 'ml-auto flex')}>
                          {flexRender(h.column.columnDef.header, h.getContext())}
                          {can && (sorted === 'asc' ? <ArrowUp className="h-3 w-3" /> : sorted === 'desc' ? <ArrowDown className="h-3 w-3" /> : <ArrowUpDown className="h-3 w-3 opacity-40" />)}
                        </button>
                      )}
                    </th>
                  )
                })}
              </tr>
            ))}
          </thead>
          <tbody>
            {table.getRowModel().rows.map((r) => (
              <tr key={r.id} onClick={() => onRowClick?.(r.original)}
                className={cn('group transition-colors', onRowClick && 'cursor-pointer hover:bg-panel-2/70')}>
                {r.getVisibleCells().map((c) => (
                  <td key={c.id} className={cn('border-b border-line/60 px-3 first:pl-5 last:pr-5', dense ? 'py-2' : 'py-3',
                    (c.column.columnDef.meta as { align?: string })?.align === 'right' && 'text-right tabular')}>
                    {flexRender(c.column.columnDef.cell, c.getContext())}
                  </td>
                ))}
              </tr>
            ))}
            {table.getRowModel().rows.length === 0 && (
              <tr><td colSpan={columns.length} className="px-5 py-10 text-center text-sm text-faint">No rows match these filters.</td></tr>
            )}
          </tbody>
        </table>
      </div>
      {pages > 1 && (
        <div className="flex items-center justify-between px-5 py-3 text-xs text-dim">
          <span>Page {table.getState().pagination.pageIndex + 1} of {pages} · {data.length} rows</span>
          <div className="flex gap-2">
            <Button variant="outline" size="sm" onClick={() => table.previousPage()} disabled={!table.getCanPreviousPage()} aria-label="Previous page"><ChevronLeft className="h-4 w-4" /></Button>
            <Button variant="outline" size="sm" onClick={() => table.nextPage()} disabled={!table.getCanNextPage()} aria-label="Next page"><ChevronRight className="h-4 w-4" /></Button>
          </div>
        </div>
      )}
    </div>
  )
}
