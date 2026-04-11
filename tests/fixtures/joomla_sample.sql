INSERT INTO `jos_categories` (`id`, `parent_id`, `title`, `alias`, `extension`) VALUES
(2, 1, 'Blog', 'blog', 'com_content'),
(3, 2, 'Updates', 'updates', 'com_content');

INSERT INTO `jos_users` (`id`, `name`, `username`) VALUES
(99, 'Site Admin', 'admin');

INSERT INTO `jos_tags` (`id`, `title`, `alias`) VALUES
(7, 'Featured', 'featured'),
(8, 'Migration', 'migration');

INSERT INTO `jos_contentitem_tag_map` (`type_alias`, `core_content_id`, `content_item_id`, `tag_id`, `type_id`) VALUES
('com_content.article', 1, 1, 7, 1),
('com_content.article', 1, 1, 8, 1);

INSERT INTO `jos_menu` (`id`, `parent_id`, `alias`, `link`, `published`) VALUES
(10, 1, 'news', 'index.php?option=com_content&view=article&id=1:hello-world&catid=3', 1);

INSERT INTO `jos_redirect_links` (`old_url`, `new_url`, `published`, `hits`) VALUES
('/old-page', '/news', 1, 4);

INSERT INTO `jos_sefurls_bak` (`id`, `cpt`, `sefurl`, `origurl`, `Itemid`, `enabled`, `priority`) VALUES
(100, 1, 'tags/seti.html', 'index.php?option=com_tags&id=101&view=tag', '', 1, 95);

INSERT INTO `jos_content` (`id`, `alias`, `title`, `introtext`, `fulltext`, `created`, `modified`, `state`, `catid`, `created_by`, `images`) VALUES
(1, 'hello-world', 'Hello World', '<p>Intro <img src="/images/hello.jpg" alt="hello"></p><p><a href="tags/seti.html">SETI</a></p>', '<p>Full body <a href="docs/spec.pdf">spec</a></p>', '2024-01-01 12:00:00', '2024-01-02 08:00:00', 1, 3, 99, '{"image_intro":"images/intro.jpg","image_fulltext":"images/full.jpg"}'),
(2, 'orphan-page', 'Orphan Page', '<p>Only intro</p>', '', '2024-02-01 12:00:00', '0000-00-00 00:00:00', 0, 2, 99, '{}');
