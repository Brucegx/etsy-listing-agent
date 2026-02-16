"use client";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { PromptCard } from "@/types";

interface PromptCardsProps {
  prompts: PromptCard[];
}

const PROMPT_TYPE_LABELS: Record<string, string> = {
  hero: "Hero Shot",
  size_reference: "Size Reference",
  wearing_a: "Wearing A",
  wearing_b: "Wearing B",
  packaging: "Packaging",
  macro_detail: "Macro Detail",
  art_still_life: "Art Still Life",
  art_abstract: "Art Abstract",
  art_flat_lay: "Flat Lay",
  scene_daily: "Scene Daily",
  workshop: "Workshop",
  materials: "Materials",
  process: "Process",
  hero_angle_b: "Hero Angle B",
  wearing_couple: "Couple Shot",
  wearing_editorial: "Editorial Shot",
  wearing_intimate: "Intimate Detail",
  art_editorial: "Art Editorial",
  color_variants: "Color Variants",
  styling_options: "Styling Options",
};

const REQUIRED_TYPES = new Set(["hero", "size_reference", "wearing_a", "wearing_b", "packaging"]);

export function PromptCards({ prompts }: PromptCardsProps) {
  return (
    <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
      {prompts.map((prompt) => (
        <Card key={prompt.index} className="flex flex-col">
          <CardHeader className="pb-2">
            <div className="flex items-center justify-between">
              <CardTitle className="text-sm">
                {prompt.type_name || PROMPT_TYPE_LABELS[prompt.type] || prompt.type}
              </CardTitle>
              <div className="flex items-center gap-1.5">
                <Badge
                  variant={REQUIRED_TYPES.has(prompt.type) ? "default" : "secondary"}
                  className="text-xs"
                >
                  {REQUIRED_TYPES.has(prompt.type) ? "Required" : "Strategic"}
                </Badge>
                <Badge variant="outline" className="text-xs">
                  #{prompt.index}
                </Badge>
              </div>
            </div>
            {prompt.goal && (
              <p className="text-xs text-muted-foreground mt-1 italic">{prompt.goal}</p>
            )}
          </CardHeader>
          <CardContent className="flex-1">
            <p className="text-xs text-muted-foreground leading-relaxed whitespace-pre-wrap max-h-48 overflow-y-auto">
              {prompt.prompt}
            </p>
            {prompt.reference_images && prompt.reference_images.length > 0 && (
              <div className="mt-2 pt-2 border-t">
                <p className="text-xs text-muted-foreground">
                  Ref images: {prompt.reference_images.join(", ")}
                </p>
              </div>
            )}
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
