export interface DiffPart {
  value: string;
  added?: boolean;
  removed?: boolean;
}

/**
 * Perform a word-level diff between two strings using LCS.
 */
export function diffWords(one: string | null | undefined, two: string | null | undefined): DiffPart[] {
  const str1 = one || "";
  const str2 = two || "";

  if (!str1 && !str2) return [];
  if (!str1) return [{ value: str2, added: true }];
  if (!str2) return [{ value: str1, removed: true }];

  // Split including whitespace and punctuation
  const words1 = str1.split(/(\s+)/).filter(Boolean);
  const words2 = str2.split(/(\s+)/).filter(Boolean);
  
  const m = words1.length;
  const n = words2.length;
  
  // Create DP table
  const dp: number[][] = Array.from({ length: m + 1 }, () => Array(n + 1).fill(0));

  for (let i = 1; i <= m; i++) {
    for (let j = 1; j <= n; j++) {
      if (words1[i - 1] === words2[j - 1]) {
        dp[i][j] = dp[i - 1][j - 1] + 1;
      } else {
        dp[i][j] = Math.max(dp[i - 1][j], dp[i][j - 1]);
      }
    }
  }

  // Backtrack to build diff
  const result: DiffPart[] = [];
  let i = m, j = n;
  while (i > 0 || j > 0) {
    if (i > 0 && j > 0 && words1[i - 1] === words2[j - 1]) {
      result.unshift({ value: words1[i - 1] });
      i--;
      j--;
    } else if (j > 0 && (i === 0 || dp[i][j - 1] >= dp[i - 1][j])) {
      result.unshift({ value: words2[j - 1], added: true });
      j--;
    } else {
      result.unshift({ value: words1[i - 1], removed: true });
      i--;
    }
  }
  return result;
}
