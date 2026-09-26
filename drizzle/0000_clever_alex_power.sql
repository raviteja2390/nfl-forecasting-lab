CREATE TABLE `boards` (
	`id` text PRIMARY KEY NOT NULL,
	`owner` text NOT NULL,
	`mode` text NOT NULL,
	`created` text NOT NULL,
	`payload` text NOT NULL
);
--> statement-breakpoint
CREATE INDEX `idx_boards_owner_mode_created` ON `boards` (`owner`,`mode`,`created`);--> statement-breakpoint
CREATE TABLE `settlements` (
	`trade_id` text PRIMARY KEY NOT NULL,
	`owner` text NOT NULL,
	`result` text NOT NULL,
	`created` text NOT NULL,
	`profit` real NOT NULL,
	`source` text NOT NULL,
	FOREIGN KEY (`trade_id`) REFERENCES `trades`(`id`) ON UPDATE no action ON DELETE no action
);
--> statement-breakpoint
CREATE TABLE `trades` (
	`id` text PRIMARY KEY NOT NULL,
	`owner` text NOT NULL,
	`board_id` text NOT NULL,
	`row_id` text NOT NULL,
	`mode` text NOT NULL,
	`created` text NOT NULL,
	`stake` real NOT NULL,
	`quote` text NOT NULL,
	`note` text NOT NULL
);
--> statement-breakpoint
CREATE INDEX `idx_trades_owner_created` ON `trades` (`owner`,`created`);--> statement-breakpoint
CREATE UNIQUE INDEX `idx_trades_owner_board_row` ON `trades` (`owner`,`board_id`,`row_id`);