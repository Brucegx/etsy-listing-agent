"use client";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import type { EtsyListing } from "@/types";

interface ListingDisplayProps {
  listing: EtsyListing;
}

export function ListingDisplay({ listing }: ListingDisplayProps) {
  const tags = listing.tags
    ? listing.tags.split(",").map((t) => t.trim()).filter(Boolean)
    : [];
  const keywords = listing.long_tail_keywords || [];
  const attributes = listing.attributes || {};

  return (
    <div className="space-y-4">
      {/* Title */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-base">Title</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-lg font-medium">{listing.title}</p>
          {listing.title_variations && listing.title_variations.length > 0 && (
            <div className="mt-2">
              <p className="text-xs text-muted-foreground mb-1">Variations:</p>
              {listing.title_variations.map((v, i) => (
                <p key={i} className="text-sm text-muted-foreground">{v}</p>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Tags */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-base">Tags ({tags.length})</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap gap-1.5">
            {tags.map((tag, i) => (
              <Badge key={i} variant="secondary" className="text-xs">
                {tag}
              </Badge>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Description */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-base">Description</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm whitespace-pre-wrap leading-relaxed">
            {listing.description}
          </p>
        </CardContent>
      </Card>

      {/* Keywords */}
      {keywords.length > 0 && (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-base">
              Long-tail Keywords ({keywords.length})
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex flex-wrap gap-1.5">
              {keywords.map((kw, i) => (
                <Badge key={i} variant="outline" className="text-xs">
                  {kw}
                </Badge>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Attributes */}
      {Object.keys(attributes).length > 0 && (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-base">Attributes</CardTitle>
          </CardHeader>
          <CardContent>
            <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
              {Object.entries(attributes).map(([key, value]) => (
                <div key={key}>
                  <dt className="text-muted-foreground capitalize">
                    {key.replace(/_/g, " ")}
                  </dt>
                  <dd className="font-medium">
                    {Array.isArray(value) ? value.join(", ") : String(value)}
                  </dd>
                </div>
              ))}
            </dl>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
